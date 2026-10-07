// ================================================
// MongoDB Initialization Script - Portal PPSA
// Cria banco de dados e collections necessárias
// ================================================

// Conectar ao banco de dados
db = db.getSiblingDB('sgppServices');

print('========================================');
print('Portal PPSA - Inicialização MongoDB');
print('========================================');

// ================================================
// Criar Collections com Validação
// ================================================

// Collection: conta_custo_oleo_entity (CCOs)
print('Criando collection: conta_custo_oleo_entity');
db.createCollection('conta_custo_oleo_entity', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['contratoCpp', 'campo', 'remessa'],
      properties: {
        contratoCpp: { bsonType: 'string' },
        campo: { bsonType: 'string' },
        remessa: { bsonType: 'string' },
        dataReconhecimento: { bsonType: 'date' },
        valorReais: { bsonType: ['decimal', 'double', 'int'] },
        tipoDocumento: { bsonType: 'string' }
      }
    }
  }
});

// Indexes para CCOs
db.conta_custo_oleo_entity.createIndex({ contratoCpp: 1, campo: 1, remessa: 1 });
db.conta_custo_oleo_entity.createIndex({ dataReconhecimento: 1 });
db.conta_custo_oleo_entity.createIndex({ tipoDocumento: 1 });

// Collection: conta_custo_oleo_corrigida_entity (CCOs Corrigidas)
print('Criando collection: conta_custo_oleo_corrigida_entity');
db.createCollection('conta_custo_oleo_corrigida_entity', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['cco_id_origem', 'session_id'],
      properties: {
        cco_id_origem: { bsonType: 'string' },
        session_id: { bsonType: 'string' },
        status_promocao: { enum: ['PENDENTE', 'PROMOVIDA', 'REJEITADA'] },
        data_correcao: { bsonType: 'date' },
        data_promocao: { bsonType: 'date' }
      }
    }
  }
});

// Indexes para CCOs Corrigidas
db.conta_custo_oleo_corrigida_entity.createIndex({ cco_id_origem: 1 });
db.conta_custo_oleo_corrigida_entity.createIndex({ session_id: 1 });
db.conta_custo_oleo_corrigida_entity.createIndex({ status_promocao: 1 });
db.conta_custo_oleo_corrigida_entity.createIndex({ contratoCpp: 1, campo: 1, remessa: 1 });

// Collection: ipca_correction_sessions (Sessões de Correção)
print('Criando collection: ipca_correction_sessions');
db.createCollection('ipca_correction_sessions', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['session_id', 'cco_id', 'user_id', 'status'],
      properties: {
        session_id: { bsonType: 'string' },
        cco_id: { bsonType: 'string' },
        user_id: { bsonType: 'string' },
        status: { enum: ['PENDING', 'APPROVED', 'REJECTED', 'APPLIED'] },
        scenario_detected: { bsonType: 'string' },
        created_at: { bsonType: 'date' },
        updated_at: { bsonType: 'date' }
      }
    }
  }
});

// Indexes para Sessions
db.ipca_correction_sessions.createIndex({ session_id: 1 }, { unique: true });
db.ipca_correction_sessions.createIndex({ cco_id: 1 });
db.ipca_correction_sessions.createIndex({ user_id: 1 });
db.ipca_correction_sessions.createIndex({ status: 1 });
db.ipca_correction_sessions.createIndex({ created_at: -1 });

// Collection: ipca_entity (Taxas IPCA)
print('Criando collection: ipca_entity');
db.createCollection('ipca_entity', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['ano', 'mes', 'taxa'],
      properties: {
        ano: { bsonType: 'int' },
        mes: { bsonType: 'int' },
        taxa: { bsonType: ['decimal', 'double'] },
        tipo: { enum: ['IPCA', 'IGPM'] }
      }
    }
  }
});

// Indexes para IPCA
db.ipca_entity.createIndex({ ano: 1, mes: 1, tipo: 1 }, { unique: true });

// Collection: igpm_entity (Taxas IGPM)
print('Criando collection: igpm_entity');
db.createCollection('igpm_entity', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      required: ['ano', 'mes', 'taxa'],
      properties: {
        ano: { bsonType: 'int' },
        mes: { bsonType: 'int' },
        taxa: { bsonType: ['decimal', 'double'] }
      }
    }
  }
});

// Indexes para IGPM
db.igpm_entity.createIndex({ ano: 1, mes: 1 }, { unique: true });

// Collection: remessa_entity (Remessas)
print('Criando collection: remessa_entity');
db.createCollection('remessa_entity', {
  validator: {
    $jsonSchema: {
      bsonType: 'object',
      properties: {
        contratoCpp: { bsonType: 'string' },
        campo: { bsonType: 'string' },
        remessa: { bsonType: 'string' },
        dataRemessa: { bsonType: 'date' }
      }
    }
  }
});

// Indexes para Remessas
db.remessa_entity.createIndex({ contratoCpp: 1, campo: 1, remessa: 1 }, { unique: true });

// ================================================
// Inserir Dados de Exemplo (Opcional)
// ================================================

// Inserir algumas taxas IPCA de exemplo
print('Inserindo dados de exemplo - IPCA');
db.ipca_entity.insertMany([
  { ano: 2023, mes: 1, taxa: NumberDecimal('0.53'), tipo: 'IPCA' },
  { ano: 2023, mes: 2, taxa: NumberDecimal('0.84'), tipo: 'IPCA' },
  { ano: 2023, mes: 3, taxa: NumberDecimal('0.71'), tipo: 'IPCA' },
  { ano: 2023, mes: 4, taxa: NumberDecimal('0.61'), tipo: 'IPCA' },
  { ano: 2023, mes: 5, taxa: NumberDecimal('0.23'), tipo: 'IPCA' },
  { ano: 2023, mes: 6, taxa: NumberDecimal('0.16'), tipo: 'IPCA' },
  { ano: 2024, mes: 1, taxa: NumberDecimal('0.42'), tipo: 'IPCA' },
  { ano: 2024, mes: 2, taxa: NumberDecimal('0.83'), tipo: 'IPCA' },
  { ano: 2024, mes: 3, taxa: NumberDecimal('0.16'), tipo: 'IPCA' },
  { ano: 2024, mes: 4, taxa: NumberDecimal('0.38'), tipo: 'IPCA' },
  { ano: 2024, mes: 5, taxa: NumberDecimal('0.46'), tipo: 'IPCA' },
  { ano: 2024, mes: 6, taxa: NumberDecimal('0.21'), tipo: 'IPCA' }
]);

// Inserir algumas taxas IGPM de exemplo
print('Inserindo dados de exemplo - IGPM');
db.igpm_entity.insertMany([
  { ano: 2023, mes: 1, taxa: NumberDecimal('0.50') },
  { ano: 2023, mes: 2, taxa: NumberDecimal('0.60') },
  { ano: 2023, mes: 3, taxa: NumberDecimal('0.70') },
  { ano: 2023, mes: 4, taxa: NumberDecimal('0.40') },
  { ano: 2023, mes: 5, taxa: NumberDecimal('0.30') },
  { ano: 2023, mes: 6, taxa: NumberDecimal('0.20') },
  { ano: 2024, mes: 1, taxa: NumberDecimal('0.45') },
  { ano: 2024, mes: 2, taxa: NumberDecimal('0.55') },
  { ano: 2024, mes: 3, taxa: NumberDecimal('0.35') },
  { ano: 2024, mes: 4, taxa: NumberDecimal('0.25') },
  { ano: 2024, mes: 5, taxa: NumberDecimal('0.40') },
  { ano: 2024, mes: 6, taxa: NumberDecimal('0.30') }
]);

// ================================================
// Verificar Collections Criadas
// ================================================
print('========================================');
print('Collections criadas:');
db.getCollectionNames().forEach(function(collection) {
  print('  - ' + collection);
});

print('========================================');
print('Inicialização concluída com sucesso!');
print('========================================');