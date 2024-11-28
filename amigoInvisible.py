#!/usr/bin/env python
# -*- coding: utf-8 -*-

import flask
from pymongo import MongoClient
from bson.objectid import ObjectId
import random
from string import ascii_letters
import datetime

import os
import yaml
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
config = yaml.safe_load(open(os.path.join(__location__,"config.yml")))

# Create the application
app = flask.Flask(__name__)

# Initialize database
client = MongoClient(config["mongo"])
db = client.amigoInvisible
amigos = db.amigos
grupos = db.grupos


@app.route('/',methods = ['GET'])
def amigo():
    user = flask.request.cookies.get('user')
    userA = flask.request.args.get('user')
    group = flask.request.args.get('group')

    resp = flask.make_response()

    # si no hay cookie de usuario o no existe ese usuario
    if ((user is None) or not amigos.find_one({ "user": user})):
        # pero sí hay argumento de usuario y existe
        if amigos.find_one({ "user": userA}):
            # escogemos como usuario el del argumento y actualizamos la cookie
            user = userA
            # borramos el usuario del parámetro para no tener que comprobar de nuevo si es el mismo
            userA = None
            resp.set_cookie('user', user, max_age=60*60*24*30*3)
        # si tampoco hay usuario en el argumento
        else:
            # si había cookie pero no era válida la borramos
            if user is not None: resp.delete_cookie('user')
            # si lo que había era un grupo en el argumento
            if ((group is not None) and grupos.find_one({ "group": group})):
                # entonces era que se registraba un nuevo usuario
                grupo = grupos.find_one({ "group": group})
                resp.set_data(flask.render_template('registro.html', group=group,nombreGrupo=grupo["nombreGrupo"]))
                return resp
            else:
                # en caso contrario la única pantalla a mostrar es la de creación
                resp.set_data(flask.render_template('creacion.html'))
                return resp
            
    # ahora user es un usuario que existe en la base de datos
    # si el usuario proviene de la cookie y en el argumento hay otro usuario válido
    if ((userA is not None) and amigos.find_one({ "user": userA}) and (user != userA)):
        resp.set_data(flask.render_template('decision.html',tipo="usuario",decisiones=[{"id":user,"nombre":amigos.find_one({ "user": user})["nombre"]},{"id":userA,"nombre":amigos.find_one({ "user": userA})["nombre"]}]))
        return resp
    
    # comprobamos si el usuario no está en ningún grupo que exista
    # (no debería pasar)
    if not any([grupos.find_one({"group":g["group"]}) for g in amigos.find({"user":user},{"group":1})]):
        for amigo in amigos.find({ "user": user}):
          # borramos todos los miembros de ese grupo que ya no existe
          amigos.delete_many({"group":amigo["group"]})
        # borramos las cookies
        resp.set_cookie('group', '', expires=0)
        resp.set_cookie('user', '', expires=0)
        # y mandamos al inicio
        resp.set_data(flask.render_template('creacion.html'))
        return resp
    ###### !!!!!!! esto no va
    print([grupos.find_one({"group":g["group"]}) for g in amigos.find({"user":user},{"group":1})])


    print("64: el group es "+str(group))
    # si no hay argumento de grupo válido
    if ((group is None) or not grupos.find_one({ "group": group})):
        # miramos a ver si hay grupo en la cookie
        group = flask.request.cookies.get('group')
        # y si no es válido entonces lo recuperamos de la base de datos
        if ((group is None) or (not amigos.find_one({ "user": user, "group": group})) or (not grupos.find_one({ "group": group}))):
            # encontramos los grupos en los que estaba el usuario
            gruposUser = [{"id":g["group"],"nombre":grupos.find_one({"group":g["group"]},{"nombreGrupo":1})["nombreGrupo"]} for g in amigos.find({"user":user},{"group":1}) if grupos.find_one({"group":g["group"]})]
            # si hay varios le damos a elegir
            if len(gruposUser) > 1:
                resp.set_data(flask.render_template('decision.html',tipo="grupo",decisiones=gruposUser))
                return resp
            # si hay uno lo marcamos como grupo
            group = gruposUser[0]["id"]
            print("79: el group es "+str(group)+ "--" + gruposUser[0]["nombre"])
    # este grupo lo guardamos como cookie (sea el del parámetro o el de la base de datos)
    # y así reiniciamos la fecha de caducidad
    resp.set_cookie('group', str(group), max_age=60*60*24)
        

    # si no existe el usuario en el grupo se le manda al registro
    # esto sucede si el usuario había participado en otros grupos
    if not amigos.find_one({ "user": user, "group":group}):
        nombre = amigos.find_one({"user":user},{"nombre":1})["nombre"]
        nombreGrupo = grupos.find_one({"group":group},{"nombreGrupo":1})["nombreGrupo"]
        resp.set_data(flask.render_template('registro.html',nombre=nombre,group=group,nombreGrupo=nombreGrupo))
        return resp

    # se le envía a espera o a resultado según corresponda
    amigo = amigos.find_one({ "user": user, "group":group})
    grupo = grupos.find_one({ "group":group})
    print("96: el grupo es "+str(grupo))
    if (amigo["siguiente"] is None):
        censo = [{"nombre":a["nombre"],"id":str(a["_id"])} for a in amigos.find({"group":group})]
        resp.set_data(flask.render_template('espera.html',nombre=amigo["nombre"],nombreGrupo=grupo["nombreGrupo"],censo=censo,maxBan=grupo["maxBan"],excluidos=amigo["excluidos"],creador=grupo["creador"] == amigo["user"]))
    else:
        # incluir el resultado final
        resp.set_data(flask.render_template('resultado.html',nombre=amigo["nombre"],nombreGrupo=grupo["nombreGrupo"],siguiente=amigo["siguiente"]))
    return resp


@app.route('/_registrando', methods = ['POST'])
def registrando():
    data = flask.request.form
    # si el nombre está escogido repetir y mostrar una notificacion toast
    if amigos.find_one({"nombre":data["nombre"],"group":data["group"]}):
        return flask.render_template('registro.html',group=data["group"],nombreGrupo=data["nombreGrupo"],err="Ya hay alguien con ese nombre en este grupo")
    # si el nombre es nuevo lo agregamos a la lista
    user = flask.request.cookies.get('user')
    if user is None:
        user = ''.join(random.choice(ascii_letters) for i in range(8))
    amigos.insert_one({"user": user, "nombre":data["nombre"], "group":data["group"], "siguiente":None, "excluidos":[] })

    # y lo guardamos como cookie
    resp = flask.make_response(flask.redirect('/'))
    resp.set_cookie('user', user, max_age=60*60*24*30*3)
    resp.set_cookie('group', data["group"], max_age=60*60*24*3)
    return resp

@app.route('/_creando', methods = ['POST'])
def creando():
    data = flask.request.form
    group = ''.join(random.choice(ascii_letters) for i in range(8))
    # si el nombre del grupo está escogido repetir y mostrar una notificacion toast
    if grupos.find_one({"nombreGrupo":data["nombreGrupo"]}):
        return flask.render_template('creacion.html',err="Ya hay un grupo con ese nombre")
    # si el usuario no es nuevo usamos su identificación
    user = flask.request.cookies.get('user')
    # y si no creamos una nueva
    if user is None:
        user = ''.join(random.choice(ascii_letters) for i in range(8))
    # lo añadimos a la lista
    amigoId = amigos.insert_one({"user": user, "nombre":data["nombre"], "group": group, "siguiente":None, "excluidos":[] })
    # amigo = amigos.find_one({"_id":ObjectId(amigoId.inserted_id)})
    # creamos el grupo
    grupos.insert_one({"group": group, "nombreGrupo":data["nombreGrupo"], "maxBan":data["maxBan"], "creador":user, "fecha":datetime.datetime.now()})

    # y guardamos todo como cookie
    resp = flask.make_response(flask.redirect('/'))
    resp.set_cookie('user', user, max_age=60*60*24*30*3)
    resp.set_cookie('group', group, max_age=60*60*24*3)
    return resp

@app.route('/_actualizar',methods = ['GET'])
def actualizar():
    print("actualizando")
    user = flask.request.args.get('user')
    group = flask.request.args.get('group')
    excluido = flask.request.args.get('excluido')
    try:
        amigo = amigos.find_one({"user":user, "group":group})
        grupo = grupos.find_one({"group":group})
    except:
        amigo = None
    if amigo is None:
        resp = flask.jsonify({"refresh":True,"censo":None})
        # borramos la cookie si la hubiera
        print("borramos el grupo de la cookie porque no se encuentra el usuario")
        resp.delete_cookie('group')
        return resp
    if amigo["siguiente"] is not None:
        resp = flask.jsonify({"refresh":True,"censo":None})
        print("ya se ha hecho el sorteo")
        return resp
    excluidos = amigo["excluidos"]
    if excluido != "0":
        print("se ha excluido a " + str(excluido))
        if not excluido in excluidos:
            excluidos = amigo["excluidos"]+[excluido]
            print("maxBan es "+str(grupo["maxBan"]))
            excluidos = excluidos[:int(grupo["maxBan"])]
        else:
            excluidos.remove(excluido)
        amigos.update_one({"user":user,"group":group},{"$set":{"excluidos":excluidos}})
    censo = [{"nombre":participante["nombre"],"id":str(participante["_id"])} for participante in amigos.find({"group":group}) if participante["_id"] != amigo["_id"]]
    print("excluidos = " + str(excluidos))
    print("censo = " + str(censo))
    return flask.jsonify({"refresh":False,"censo":censo,"excluidos":excluidos})

@app.route('/_sortear',methods = ['GET'])
def sorteo():
    user = flask.request.args.get('user')
    group = flask.request.args.get('group')
    print('realizando el sorteo')
    try:
        amigo = amigos.find_one({"user":user, "group":group})
        grupo = grupos.find_one({"group":group})
        if grupo["creador"] != amigo["user"]: flask.jsonify({"respuesta":False})

        ids = [str(id) for id in amigos.find({"group":group}).distinct('_id')]
        random.shuffle(ids)



        intentos = 0
        while any([ids[index-1] in amigos.find_one({"_id":ObjectId(ids[index])})["excluidos"] for index in range(len(ids))]) and intentos < 1000:
            random.shuffle(ids)
            intentos += 1


        if intentos >= 1000: flask.jsonify({"respuesta":False})

        for index in range(len(ids)):
            amigos.update_one({"_id":ObjectId(ids[index]),"group":group},{"$set": {"siguiente":amigos.find_one({"_id":ObjectId(ids[index-1]),"group":group})["nombre"]}})
        return flask.jsonify({"respuesta":True})
    except:
        return flask.jsonify({"respuesta":False})
    pass

@app.route('/_consultaGrupos',methods = ['GET'])
def consultaGrupos():
    user = flask.request.args.get('user')
    grupos = [g["group"] for g in amigos.find({"user":user},{"group":1})]

    return flask.jsonify({"respuesta":len(grupos) != 1})

if __name__ == "__main__":
    app.run()
