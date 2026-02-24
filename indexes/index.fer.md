# FER Database Indexes

Recommended index configurations for `FER` database collections to optimize query performance, following MongoDB best practices (ESR rule, redundancy avoidance).

## Design Considerations
- **Primary Keys**: MongoDB automatically indexes `_id`. Separate `id` fields (e.g., from Cosmos DB) should be mapped to `_id` or indexed with a unique constraint to prevent redundant primary key indexes.
- **Compound Indexes**: Indexes should be aligned with common query patterns (Equality → Sort → Range). A single compound index can often replace multiple single-field indexes.
- **Array Indexing**: Indexing fields within unbounded arrays (e.g., `Annotations`, `evidences`, `templateElements`) results in multikey indexes, which increase write costs.

## Database: FER

### Collection: `fer.UserAnnotations`
*Content*: User-created annotations on documents with highlights and tags.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key (if not using `_id`).
*   **Index**: `{UserId: 1, CreatedOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves recent annotations for a specific user.
*   **Index**: `{FileId: 1, CreatedOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves annotations for a document, sorted by creation date.
*   **Index**: `{FileId: 1, "Annotations.AnnotationId": 1}`
    *   **Type**: Compound (Multikey)
    *   **Rationale**: Supports lookup of nested annotations by `AnnotationId` within a file scope.

### Collection: `fer.UserProfiles`
*Content*: User profile configurations, group memberships, and template access.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `userId`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Lookup by user profile ID.
*   **Index**: `userName`
    *   **Type**: Single Field
    *   **Rationale**: Exact-match lookups. *Atlas Search is recommended for free-text search.*
*   **Index**: `userGroups`
    *   **Type**: Multikey (Array)
    *   **Rationale**: Supports filtering users by group membership.
*   **Index**: `updatedOn`
    *   **Type**: Single Field
    *   **Rationale**: Tracks profile updates.
*   **Index**: `userTemplates.templateId`
    *   **Type**: Single Field
    *   **Rationale**: Retrieval of users with specific template access.

### Collection: `fer.UserSearchTerms`
*Content*: User search history tracking.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `{userId: 1, datetime: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves recent search history for a user.

### Collection: `fer.annotations`
*Content*: Document annotations with highlights and text extractions.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `{fileId: 1, UpdatedOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves annotations by file, sorted by newest first.
*   **Index**: `{UserId: 1, UpdatedOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves recent annotation activity by user.
*   **Index**: `{summaryInstanceId: 1, UpdatedOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves recent activity for a summary instance.
*   **Index**: `{fileId: 1, "Annotations.TagId": 1}`
    *   **Type**: Compound (Multikey)
    *   **Rationale**: Supports filtering by tag within a file.

### Collection: `fer.authorizationResponses`
*Content*: Authorization determination responses.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `{CreatedBy: 1, CreatedOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieval of audit/review history by creator.
*   **Index**: `{UpdatedBy: 1, UpdatedOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieval of recently updated records by user.

### Collection: `fer.document_evidence`
*Content*: Extracted clinical evidence linked to documents.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `{documentId: 1, criteriaId: 1, createdDate: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieves evidence for a document/criteria, sorted by date.
*   **Index**: `{documentId: 1, "evidences.tagId": 1}`
    *   **Type**: Compound (Multikey)
    *   **Rationale**: Supports filtering by tag within a document.
*   **Index**: `{documentId: 1, "evidences.evidenceId": 1}`
    *   **Type**: Compound (Multikey)
    *   **Rationale**: Lookup of `evidenceId` scoped to a document.
*   **Index**: `{documentId: 1, criteriaId: 1, "evidences.evidenceNodes.text": "text"}`
    *   **Type**: Compound (Text)
    *   **Rationale**: Text search constrained to a document/criteria. *Atlas Search is recommended for complex queries.*

### Collection: `fer.guidelinerecord`
*Content*: Clinical guideline definitions.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `{guidelineId: 1, guidelineVersion: 1}`
    *   **Type**: Compound
    *   **Rationale**: Lookup of specific guideline versions.
*   **Index**: `{guidelineId: 1, guidelineVersion: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieval of the latest version for a guideline.
*   **Index**: `{orgCode: 1, pubCode: 1, guidelineVersion: -1}`
    *   **Type**: Compound
    *   **Rationale**: Browsing latest guidelines by organization/publication.
*   **Index**: `guidelineName`
    *   **Type**: Single Field
    *   **Rationale**: Exact-match lookups.

### Collection: `fer.modelfeedback`
*Content*: User feedback on AI/ML model predictions.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `feedbackId`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Unique feedback identifier.
*   **Index**: `{authId: 1, CriteriaId: 1, CreatedAt: -1}`
    *   **Type**: Compound
    *   **Rationale**: Feedback retrieval for auth/criteria, sorted by date.
*   **Index**: `{DocId: 1, CreatedAt: -1}`
    *   **Type**: Compound
    *   **Rationale**: Feedback history for a document.
*   **Index**: `{UserId: 1, CreatedAt: -1}`
    *   **Type**: Compound
    *   **Rationale**: Recent feedback by user.
*   **Index**: `{AIModelName: 1, CreatedAt: -1}`
    *   **Type**: Compound
    *   **Rationale**: Model performance monitoring.

### Collection: `fer.source_nlp_xref`
*Content*: Cross-reference between source systems and NLP documents.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `sourceId`
    *   **Type**: Single Field
    *   **Rationale**: Source identifier lookup.
*   **Index**: `nlpDocumentId`
    *   **Type**: Single Field
    *   **Rationale**: Link to NLP document.
*   **Index**: `metadata.memberId`
    *   **Type**: Single Field
    *   **Rationale**: Member lookup.
*   **Index**: `metadata.encounterId`
    *   **Type**: Single Field
    *   **Rationale**: Encounter lookup.
*   **Index**: `{sourceCode: 1, ingestedDate: -1}`
    *   **Type**: Compound
    *   **Rationale**: Recent ingested records by source.

> **Note**: For member name searches (e.g. `metadata.memberName`), Atlas Search is recommended over standard MongoDB text indexes.

### Collection: `fer.summary_templates`
*Content*: Summary form templates.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `templateId`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Template identifier lookup.
*   **Index**: `{templateId: 1, templateVersion: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieval of latest template versions.
*   **Index**: `templateName`
    *   **Type**: Single Field
    *   **Rationale**: Exact-match lookups.
*   **Index**: `allowedTags`
    *   **Type**: Multikey (Array)
    *   **Rationale**: Filtering templates by allowed tags.
*   **Index**: `templateElements.key`
    *   **Type**: Single Field (Multikey)
    *   **Rationale**: querying elements by key across the collection.

### Collection: `fer.tags`
*Content*: Tag taxonomy definitions.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `TagId`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Tag identifier lookup.
*   **Index**: `ShortDesc`
    *   **Type**: Single Field
    *   **Rationale**: Exact-match lookups.
*   **Index**: `LongDesc`
    *   **Type**: Single Field
    *   **Rationale**: Exact-match lookups.
*   **Index**: `SortOrder`
    *   **Type**: Single Field
    *   **Rationale**: Sorting tags by order.
*   **Index**: `DisabledOn`
    *   **Type**: Single Field
    *   **Rationale**: Filtering disabled tags.

### Collection: `fer.tags_v2`
*Content*: Extended tag definitions (v2).

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `tagId`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Tag identifier lookup.
*   **Index**: `{tagCategory: 1, priority: 1}`
    *   **Type**: Compound
    *   **Rationale**: Category browsing sorted by priority.
*   **Index**: `{sourceCode: 1, tagCategory: 1, priority: 1}`
    *   **Type**: Compound
    *   **Rationale**: Per-source category browsing sorted by priority.
*   **Index**: `tagName`
    *   **Type**: Single Field
    *   **Rationale**: Exact-match lookups.
*   **Index**: `disabledOn`
    *   **Type**: Single Field
    *   **Rationale**: Filtering disabled tags.

### Collection: `fer.templateTableData`
*Content*: Table-based summary data.

*   **Index**: `id`
    *   **Type**: Single Field (Unique)
    *   **Rationale**: Primary lookup key.
*   **Index**: `{authId: 1, summaryInstanceId: 1, createdOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Tables sorted by date for auth/summary.
*   **Index**: `{summaryInstanceId: 1, createdOn: -1}`
    *   **Type**: Compound
    *   **Rationale**: Retrieval of table data by summary instance.
*   **Index**: `tables.tableId`
    *   **Type**: Single Field (Multikey)
    *   **Rationale**: Nested table lookup by ID.