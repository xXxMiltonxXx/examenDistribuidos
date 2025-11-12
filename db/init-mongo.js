// Inicializa la base de datos y datos de ejemplo
// Se ejecuta automáticamente por el contenedor de MongoDB

const dbName = 'clientes_db';
const colName = 'personas';

const db = new Mongo().getDB(dbName);

db.createCollection(colName);

db.getCollection(colName).insertMany([
  { cedula: '1234567890', nombres: 'Juan', apellidos: 'Nieve', saldo: 150.75 },
  { cedula: '1111111111', nombres: 'Ana', apellidos: 'Pérez', saldo: 300 },
  { cedula: '2222222222', nombres: 'Luis', apellidos: 'Gómez', saldo: 80.5 },
]);

print(`Base de datos '${dbName}' inicializada con colección '${colName}'.`);