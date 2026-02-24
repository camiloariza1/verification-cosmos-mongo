/* eslint-disable no-undef */
/**
 * Usage:
 *   mongosh "<connection-string>" indexes/create_nlp_indexes.mongosh.js
 *
 * Applies recommended indexes for NLP-related collections.
 */

function createIndexSafe(dbName, collName, key, options) {
  const coll = db.getSiblingDB(dbName).getCollection(collName);
  try {
    const indexName = coll.createIndex(key, options || {});
    print(`[OK] ${dbName}.${collName} -> ${indexName}`);
  } catch (err) {
    print(`[ERROR] ${dbName}.${collName} -> ${tojson(key)} :: ${err.message}`);
  }
}

function createUniqueOnFirstExistingField(dbName, collName, fields, indexName) {
  const coll = db.getSiblingDB(dbName).getCollection(collName);

  let chosen = null;

  // Reuse an already-existing unique single-field index if present.
  const existingIndexes = coll.getIndexes();
  for (const field of fields) {
    const hasUnique = existingIndexes.some((idx) => {
      const keys = Object.keys(idx.key || {});
      return idx.unique === true && keys.length === 1 && idx.key[field] === 1;
    });
    if (hasUnique) {
      chosen = field;
      break;
    }
  }

  // Otherwise choose the first field that actually exists in documents.
  if (!chosen) {
    for (const field of fields) {
      const probe = {};
      probe[field] = { $exists: true };
      if (coll.findOne(probe)) {
        chosen = field;
        break;
      }
    }
  }

  // Fallback to first candidate if collection is empty or field not found yet.
  if (!chosen) {
    chosen = fields[0];
    print(`[WARN] ${dbName}.${collName}: no candidate field found in data, defaulting to "${chosen}"`);
  }

  const key = {};
  key[chosen] = 1;
  createIndexSafe(dbName, collName, key, { name: indexName, unique: true });
}

const plans = [
  {
    dbName: "NLP",
    collName: "asyncpipeline.metadata",
    indexes: [
      { key: { document_id: 1 }, options: { name: "ux_document_id", unique: true } },
      {
        key: { group: 1, ingest_date: 1 },
        options: {
          name: "idx_group_ingest_date_incomplete",
          partialFilterExpression: { is_complete: false, did_error: false },
        },
      },
    ],
  },
  {
    dbName: "NLP",
    collName: "asyncpipeline-ocr.metadata",
    indexes: [
      { key: { document_id: 1 }, options: { name: "ux_document_id", unique: true } },
      {
        key: { group: 1, ingest_date: 1 },
        options: {
          name: "idx_group_ingest_date_incomplete",
          partialFilterExpression: { is_complete: false, did_error: false },
        },
      },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member.auth",
    indexes: [
      { key: { auth_id: 1, ingestion_date: -1 }, options: { name: "idx_auth_id_ingestion_date" } },
      { key: { src_subs_hippa_id: 1, ingestion_date: -1 }, options: { name: "idx_member_id_ingestion_date" } },
      { key: { auth_status_desc: 1, ingestion_date: -1 }, options: { name: "idx_auth_status_ingestion_date" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member.auth_qnr_match",
    indexes: [
      { key: { auth_id: 1, ingestion_date: -1 }, options: { name: "idx_auth_id_ingestion_date" } },
      { key: { ingestion_date: -1 }, options: { name: "idx_ingestion_date" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member.auth_snapshot_baseline",
    indexes: [
      { key: { auth_id: 1 }, options: { name: "ux_auth_id", unique: true } },
      { key: { src_subs_hippa_id: 1, ingestion_date: -1 }, options: { name: "idx_member_id_ingestion_date" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-kafka.auth",
    indexes: [
      { key: { auth_id: 1, ingestion_date: -1 }, options: { name: "idx_auth_id_ingestion_date" } },
      { key: { src_subs_hippa_id: 1, ingestion_date: -1 }, options: { name: "idx_member_id_ingestion_date" } },
      { key: { auth_status_desc: 1, ingestion_date: -1 }, options: { name: "idx_auth_status_ingestion_date" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-kafka.auth_qnr_match",
    indexes: [
      { key: { auth_id: 1, ingestion_date: -1 }, options: { name: "idx_auth_id_ingestion_date" } },
      { key: { ingestion_date: -1 }, options: { name: "idx_ingestion_date" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-kafka.cgx_managed",
    alternateUnique: { fields: ["id", "hashed_key"], indexName: "ux_primary_key" },
    indexes: [
      {
        key: { auth_id: 1, ingestion_date: -1 },
        options: { name: "idx_auth_id_ingestion_date_not_voided", partialFilterExpression: { voided: false } },
      },
      { key: { uuid: 1 }, options: { name: "idx_uuid" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-kafka.cgx_void_feed",
    alternateUnique: { fields: ["id", "hashed_key"], indexName: "ux_primary_key" },
    indexes: [
      {
        key: { auth_id: 1, ingestion_date: -1 },
        options: {
          name: "idx_auth_id_ingestion_date_pending_update",
          partialFilterExpression: { has_updated_managed_record: false },
        },
      },
      { key: { uuid: 1 }, options: { name: "idx_uuid" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-kafka.facility_state",
    indexes: [
      { key: { hashed_key: 1 }, options: { name: "ux_hashed_key", unique: true } },
      { key: { auth_id: 1, isonow_timestamp: -1 }, options: { name: "idx_auth_id_isonow_timestamp" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-kafka.mq_auth_log",
    indexes: [
      {
        key: { "MemberInformation.MemberId": 1, "ContactInformation.CreatedDate": -1 },
        options: { name: "idx_member_id_created_date" },
      },
      { key: { "MemberInformation.SubscriberId": 1 }, options: { name: "idx_subscriber_id" } },
      { key: { "ContactInformation.CreatedDate": 1 }, options: { name: "idx_created_date" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-pco.adt_messages_cache",
    indexes: [
      { key: { admit_key: 1 }, options: { name: "idx_admit_key" } },
      { key: { mstr_demogr_id: 1, load_date: -1 }, options: { name: "idx_demogr_id_load_date" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-pco.athena_documents_cache",
    indexes: [
      { key: { patient_id: 1, created_date_time: -1 }, options: { name: "idx_patient_id_created_date_time" } },
      { key: { doc_id: 1 }, options: { name: "idx_doc_id" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-pco.documents_cache",
    indexes: [
      { key: { patient_key: 1, load_ts: -1 }, options: { name: "idx_patient_key_load_ts" } },
      { key: { doc_id: 1 }, options: { name: "idx_doc_id" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-member-pco.referral_claim_pcp_combined",
    indexes: [
      {
        key: { "MemberInformation.MemberId": 1, "ContactInformation.CreatedDate": -1 },
        options: { name: "idx_member_id_created_date" },
      },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-pharmacy-member.member_data",
    indexes: [
      { key: { sdr_person_id: 1 }, options: { name: "idx_sdr_person_id" } },
      { key: { src_subs_hippa_id: 1 }, options: { name: "idx_src_subs_hippa_id" } },
    ],
  },
  {
    dbName: "NLP",
    collName: "nlp-pharmacy-member.model_output",
    indexes: [
      { key: { uuid: 1 }, options: { name: "idx_uuid" } },
      { key: { "data.last_modified": 1 }, options: { name: "idx_data_last_modified" } },
    ],
  },
];

print("Starting NLP index creation...");
for (const plan of plans) {
  print(`\n=== ${plan.dbName}.${plan.collName} ===`);
  if (plan.alternateUnique) {
    createUniqueOnFirstExistingField(
      plan.dbName,
      plan.collName,
      plan.alternateUnique.fields,
      plan.alternateUnique.indexName
    );
  }
  for (const idx of plan.indexes) {
    createIndexSafe(plan.dbName, plan.collName, idx.key, idx.options);
  }
}
print("\nNLP index creation script completed.");
