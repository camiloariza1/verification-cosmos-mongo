# CW Milan Database Indexes

Recommended index configurations for `CW Milan` database collections to optimize query performance, following MongoDB best practices (ESR rule, redundancy avoidance).

## Design Considerations
- **Primary Keys**: MongoDB automatically indexes `_id`. Where feasible, legacy `id` fields should be mapped to `_id` to avoid redundant uniqueness indexes.
- **Array Indexing**: Indexing fields within unbounded arrays (e.g., `evidences`, `summaryItems`) results in multikey indexes, which impact write performance and storage.
- **Compound Indexes**: Indexes are designed to support specific query patterns (Equality, Sort, Range).

## Database: CW Milan

### Collection: `cw-milan.cw_document_evidence`
*Content*: Extracted clinical evidence from documents with AI confidence scores.

*   **Index**: `{documentId: 1, criteriaId: 1}`
    *   **Type**: Compound
    *   **Rationale**: Supports fetching evidence by document and criteria (primary access pattern).
*   **Index**: `{documentId: 1, "evidences.tagId": 1}`
    *   **Type**: Compound (Multikey)
    *   **Rationale**: Supports filtering by tag within a specific document.
*   **Index**: `{documentId: 1, "evidences.evidenceId": 1}`
    *   **Type**: Compound (Multikey)
    *   **Rationale**: Supports lookup of specific evidence IDs within a document scope.
*   **Index**: `{documentId: 1, criteriaId: 1, "evidences.evidenceNodes.text": "text"}`
    *   **Type**: Compound (Text)
    *   **Rationale**: Enables text search constrained to a document/criteria context. *Atlas Search is recommended for complex full-text requirements.*

### Collection: `cw-milan.cw_model_feedback`
*Content*: User feedback on AI model predictions.

*   **Index**: `{sourceDocumentId: 1, createdOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves feedback for a source document, sorted by newest first.
*   **Index**: `{nlpDocumentId: 1, createdOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves feedback for an NLP document, sorted by newest first.
*   **Index**: `{userId: 1, createdOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves recent feedback by user.
*   **Index**: `{aimodelName: 1, createdOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Supports analysis of model performance over time.

### Collection: `cw-milan.cw_source_nlp_xref`
*Content*: Cross-reference between source clinical systems and NLP-processed documents.

*   **Index**: `sourceDocumentId`
    *   **Type**: Single Field (Unique per source)
    *   **Rationale**: Lookup by source document ID.
*   **Index**: `nlpDocumentId`
    *   **Type**: Single Field
    *   **Rationale**: Lookup by NLP document ID.
*   **Index**: `nlpIdentifier`
    *   **Type**: Single Field
    *   **Rationale**: Lookup by NLP identifier.
*   **Index**: `metadata.encounterId`
    *   **Type**: Single Field
    *   **Rationale**: Lookup by encounter ID.
*   **Index**: `{sourceCode: 1, ingestedDate: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves recently ingested records filtered by source.

> **Note**: For name-based searches (e.g., `metadata.patientName`), Atlas Search is recommended over standard MongoDB text indexes.

### Collection: `cw-milan.cw_summary_item`
*Content*: Summary items extracted from documents.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `{sourceId: 1, summaryInstanceId: 1, createdOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves the latest summary items for a source and instance.
*   **Index**: `summaryItems.id`
    *   **Type**: Single Field
    *   **Rationale**: Lookup by summary item ID.
*   **Index**: `summaryItems.templateId`
    *   **Type**: Single Field (Multikey)
    *   **Rationale**: Supports querying for summaries containing a specific template ID.