const dbName = "amigoInvisible";

const database = db.getSiblingDB(dbName);

database.createCollection("grupos");
database.createCollection("amigos");
