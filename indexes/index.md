# NLP Database Indexes

Recommended index configurations for `NLP` database collections to optimize query performance, adhering to MongoDB best practices (ESR rule, redundancy avoidance).

## Design Considerations
- **Primary Keys**: MongoDB automatically indexes `_id`. Where `id` or `document_id` serve as primary identifiers, they should reside in `_id` to avoid redundant indexes.
- **Compound Indexes**: Indexes should match query shape (Equality → Sort → Range).
- **Partial Indexes**: Utilized for queue-style workflows (e.g., “incomplete only”) to minimize index size.

## Database: NLP

### Collection: `asyncpipeline.metadata`
*   **Index**: `document_id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key (if not using `_id`).
*   **Index**: `{group: 1, ingest_date: 1}`
    *   **Properties**: `partialFilterExpression: { is_complete: false, did_error: false }`
    *   **Rationale**: Processing queue by group (FIFO), excluding completed/errored items.

### Collection: `asyncpipeline-ocr.metadata`
*   **Index**: `document_id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `{group: 1, ingest_date: 1}`
    *   **Properties**: `partialFilterExpression: { is_complete: false, did_error: false }`
    *   **Rationale**: Processing queue by group (FIFO), excluding completed/errored items.

### Collection: `nlp-member.auth`
*   **Index**: `{auth_id: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Auth lookup and retrieval of latest record by ingestion date.
*   **Index**: `{src_subs_hippa_id: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Member history sorted by date.
*   **Index**: `{auth_status_desc: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Operational queue (e.g., status-based retrieval).

### Collection: `nlp-member.auth_qnr_match`
*   **Index**: `{auth_id: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieval of the newest match record for an auth.
*   **Index**: `{ingestion_date: -1}`
    *   **Type**: Single Field
    *   **Rationale**: Supports global retention/pruning operations.

### Collection: `nlp-member.auth_snapshot_baseline`
*   **Index**: `auth_id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Baseline lookup.
*   **Index**: `{src_subs_hippa_id: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Member baseline history, newest first.

### Collection: `nlp-member-kafka.auth`
*   **Index**: `{auth_id: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Auth lookup and retrieval of latest record.
*   **Index**: `{src_subs_hippa_id: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Member history.
*   **Index**: `{auth_status_desc: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Status queue.

### Collection: `nlp-member-kafka.auth_qnr_match`
*   **Index**: `{auth_id: 1, ingestion_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieval of the newest match record for an auth.
*   **Index**: `{ingestion_date: -1}`
    *   **Type**: Single Field
    *   **Rationale**: Supports global retention/pruning operations.

### Collection: `nlp-member-kafka.cgx_managed`
*   **Index**: `id` or `hashed_key`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Natural unique key.
*   **Index**: `{auth_id: 1, ingestion_date: -1}`
    *   **Properties**: `partialFilterExpression: { voided: false }`
    *   **Rationale**: Lookup for active/non-voided records for an auth, newest first.
*   **Index**: `{uuid: 1}`
    *   **Type**: Single Field
    *   **Rationale**: Retrieval by UUID.

### Collection: `nlp-member-kafka.cgx_void_feed`
*   **Index**: `id` or `hashed_key`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Natural unique key.
*   **Index**: `{auth_id: 1, ingestion_date: -1}`
    *   **Properties**: `partialFilterExpression: { has_updated_managed_record: false }`
    *   **Rationale**: Queue of void-feed records requiring follow-up.
*   **Index**: `{uuid: 1}`
    *   **Type**: Single Field
    *   **Rationale**: Retrieval by UUID.

### Collection: `nlp-member-kafka.facility_state`
*   **Index**: `hashed_key`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Natural unique key.
*   **Index**: `{auth_id: 1, isonow_timestamp: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieval of the latest facility state for an auth.

### Collection: `nlp-member-kafka.mq_auth_log`
*   **Index**: `{MemberInformation.MemberId: 1, ContactInformation.CreatedDate: -1}`
    *   **Type**: Compound
    *   **Rationale**: Member logs sorted by date.
*   **Index**: `MemberInformation.SubscriberId`
    *   **Type**: Single Field
    *   **Rationale**: Subscriber lookup.
*   **Index**: `ContactInformation.CreatedDate`
    *   **Type**: Single Field
    *   **Rationale**: Global log retrieval by date.

### Collection: `nlp-member-pco.adt_messages_cache`
*   **Index**: `admit_key`
    *   **Type**: Single Field
    *   **Rationale**: Lookup.
*   **Index**: `{mstr_demogr_id: 1, load_date: -1}`
    *   **Type**: Compound
    *   **Rationale**: Demographics history, newest first.

### Collection: `nlp-member-pco.athena_documents_cache`
*   **Index**: `{patient_id: 1, created_date_time: -1}`
    *   **Type**: Compound
    *   **Rationale**: Patient documents sorted by creation.
*   **Index**: `doc_id`
    *   **Type**: Single Field
    *   **Rationale**: Lookup.

### Collection: `nlp-member-pco.documents_cache`
*   **Index**: `{patient_key: 1, load_ts: -1}`
    *   **Type**: Compound
    *   **Rationale**: Patient document timeline.
*   **Index**: `doc_id`
    *   **Type**: Single Field
    *   **Rationale**: Lookup.

### Collection: `nlp-member-pco.referral_claim_pcp_combined`
*   **Index**: `{MemberInformation.MemberId: 1, ContactInformation.CreatedDate: -1}`
    *   **Type**: Compound
    *   **Rationale**: History.

### Collection: `nlp-pharmacy-member.member_data`
*   **Index**: `sdr_person_id`
    *   **Type**: Single Field
    *   **Rationale**: Lookup (high-cardinality).
*   **Index**: `src_subs_hippa_id`
    *   **Type**: Single Field
    *   **Rationale**: Lookup.

### Collection: `nlp-pharmacy-member.model_output`
*   **Index**: `uuid`
    *   **Type**: Single Field
    *   **Rationale**: Unique ID.
*   **Index**: `data.last_modified`
    *   **Type**: Single Field
    *   **Rationale**: Freshness check.