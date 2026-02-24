// Copy/paste into an open mongosh session.
// All commands target the NLP database.
use("NLP");

// asyncpipeline.metadata
db.getCollection("asyncpipeline.metadata").createIndex(
  { document_id: 1 },
  { name: "ux_document_id", unique: true }
);
db.getCollection("asyncpipeline.metadata").createIndex(
  { group: 1, ingest_date: 1 },
  {
    name: "idx_group_ingest_date_incomplete",
    partialFilterExpression: { is_complete: false, did_error: false },
  }
);

// asyncpipeline-ocr.metadata
db.getCollection("asyncpipeline-ocr.metadata").createIndex(
  { document_id: 1 },
  { name: "ux_document_id", unique: true }
);
db.getCollection("asyncpipeline-ocr.metadata").createIndex(
  { group: 1, ingest_date: 1 },
  {
    name: "idx_group_ingest_date_incomplete",
    partialFilterExpression: { is_complete: false, did_error: false },
  }
);

// nlp-member.auth
db.getCollection("nlp-member.auth").createIndex(
  { auth_id: 1, ingestion_date: -1 },
  { name: "idx_auth_id_ingestion_date" }
);
db.getCollection("nlp-member.auth").createIndex(
  { src_subs_hippa_id: 1, ingestion_date: -1 },
  { name: "idx_member_id_ingestion_date" }
);
db.getCollection("nlp-member.auth").createIndex(
  { auth_status_desc: 1, ingestion_date: -1 },
  { name: "idx_auth_status_ingestion_date" }
);

// nlp-member.auth_qnr_match
db.getCollection("nlp-member.auth_qnr_match").createIndex(
  { auth_id: 1, ingestion_date: -1 },
  { name: "idx_auth_id_ingestion_date" }
);
db.getCollection("nlp-member.auth_qnr_match").createIndex(
  { ingestion_date: -1 },
  { name: "idx_ingestion_date" }
);

// nlp-member.auth_snapshot_baseline
db.getCollection("nlp-member.auth_snapshot_baseline").createIndex(
  { auth_id: 1 },
  { name: "ux_auth_id", unique: true }
);
db.getCollection("nlp-member.auth_snapshot_baseline").createIndex(
  { src_subs_hippa_id: 1, ingestion_date: -1 },
  { name: "idx_member_id_ingestion_date" }
);

// nlp-member-kafka.auth
db.getCollection("nlp-member-kafka.auth").createIndex(
  { auth_id: 1, ingestion_date: -1 },
  { name: "idx_auth_id_ingestion_date" }
);
db.getCollection("nlp-member-kafka.auth").createIndex(
  { src_subs_hippa_id: 1, ingestion_date: -1 },
  { name: "idx_member_id_ingestion_date" }
);
db.getCollection("nlp-member-kafka.auth").createIndex(
  { auth_status_desc: 1, ingestion_date: -1 },
  { name: "idx_auth_status_ingestion_date" }
);

// nlp-member-kafka.auth_qnr_match
db.getCollection("nlp-member-kafka.auth_qnr_match").createIndex(
  { auth_id: 1, ingestion_date: -1 },
  { name: "idx_auth_id_ingestion_date" }
);
db.getCollection("nlp-member-kafka.auth_qnr_match").createIndex(
  { ingestion_date: -1 },
  { name: "idx_ingestion_date" }
);

// nlp-member-kafka.cgx_managed
// Choose ONE of the next two unique indexes (id OR hashed_key), then run it.
// db.getCollection("nlp-member-kafka.cgx_managed").createIndex(
//   { id: 1 },
//   { name: "ux_primary_key", unique: true }
// );
// db.getCollection("nlp-member-kafka.cgx_managed").createIndex(
//   { hashed_key: 1 },
//   { name: "ux_primary_key", unique: true }
// );
db.getCollection("nlp-member-kafka.cgx_managed").createIndex(
  { auth_id: 1, ingestion_date: -1 },
  {
    name: "idx_auth_id_ingestion_date_not_voided",
    partialFilterExpression: { voided: false },
  }
);
db.getCollection("nlp-member-kafka.cgx_managed").createIndex(
  { uuid: 1 },
  { name: "idx_uuid" }
);

// nlp-member-kafka.cgx_void_feed
// Choose ONE of the next two unique indexes (id OR hashed_key), then run it.
// db.getCollection("nlp-member-kafka.cgx_void_feed").createIndex(
//   { id: 1 },
//   { name: "ux_primary_key", unique: true }
// );
// db.getCollection("nlp-member-kafka.cgx_void_feed").createIndex(
//   { hashed_key: 1 },
//   { name: "ux_primary_key", unique: true }
// );
db.getCollection("nlp-member-kafka.cgx_void_feed").createIndex(
  { auth_id: 1, ingestion_date: -1 },
  {
    name: "idx_auth_id_ingestion_date_pending_update",
    partialFilterExpression: { has_updated_managed_record: false },
  }
);
db.getCollection("nlp-member-kafka.cgx_void_feed").createIndex(
  { uuid: 1 },
  { name: "idx_uuid" }
);

// nlp-member-kafka.facility_state
db.getCollection("nlp-member-kafka.facility_state").createIndex(
  { hashed_key: 1 },
  { name: "ux_hashed_key", unique: true }
);
db.getCollection("nlp-member-kafka.facility_state").createIndex(
  { auth_id: 1, isonow_timestamp: -1 },
  { name: "idx_auth_id_isonow_timestamp" }
);

// nlp-member-kafka.mq_auth_log
db.getCollection("nlp-member-kafka.mq_auth_log").createIndex(
  { "MemberInformation.MemberId": 1, "ContactInformation.CreatedDate": -1 },
  { name: "idx_member_id_created_date" }
);
db.getCollection("nlp-member-kafka.mq_auth_log").createIndex(
  { "MemberInformation.SubscriberId": 1 },
  { name: "idx_subscriber_id" }
);
db.getCollection("nlp-member-kafka.mq_auth_log").createIndex(
  { "ContactInformation.CreatedDate": 1 },
  { name: "idx_created_date" }
);

// nlp-member-pco.adt_messages_cache
db.getCollection("nlp-member-pco.adt_messages_cache").createIndex(
  { admit_key: 1 },
  { name: "idx_admit_key" }
);
db.getCollection("nlp-member-pco.adt_messages_cache").createIndex(
  { mstr_demogr_id: 1, load_date: -1 },
  { name: "idx_demogr_id_load_date" }
);

// nlp-member-pco.athena_documents_cache
db.getCollection("nlp-member-pco.athena_documents_cache").createIndex(
  { patient_id: 1, created_date_time: -1 },
  { name: "idx_patient_id_created_date_time" }
);
db.getCollection("nlp-member-pco.athena_documents_cache").createIndex(
  { doc_id: 1 },
  { name: "idx_doc_id" }
);

// nlp-member-pco.documents_cache
db.getCollection("nlp-member-pco.documents_cache").createIndex(
  { patient_key: 1, load_ts: -1 },
  { name: "idx_patient_key_load_ts" }
);
db.getCollection("nlp-member-pco.documents_cache").createIndex(
  { doc_id: 1 },
  { name: "idx_doc_id" }
);

// nlp-member-pco.referral_claim_pcp_combined
db.getCollection("nlp-member-pco.referral_claim_pcp_combined").createIndex(
  { "MemberInformation.MemberId": 1, "ContactInformation.CreatedDate": -1 },
  { name: "idx_member_id_created_date" }
);

// nlp-pharmacy-member.member_data
db.getCollection("nlp-pharmacy-member.member_data").createIndex(
  { sdr_person_id: 1 },
  { name: "idx_sdr_person_id" }
);
db.getCollection("nlp-pharmacy-member.member_data").createIndex(
  { src_subs_hippa_id: 1 },
  { name: "idx_src_subs_hippa_id" }
);

// nlp-pharmacy-member.model_output
db.getCollection("nlp-pharmacy-member.model_output").createIndex(
  { uuid: 1 },
  { name: "idx_uuid" }
);
db.getCollection("nlp-pharmacy-member.model_output").createIndex(
  { "data.last_modified": 1 },
  { name: "idx_data_last_modified" }
);
