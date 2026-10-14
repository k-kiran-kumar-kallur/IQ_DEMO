# Enterprise IQ: how files are stored and how questions are answered

As of 12 Oct 2026 · pilot build (`backend/`, `frontend/`)

## 1. The idea in one paragraph

Every file is loaded once and stored in three places, each chosen for one job.

| Store | What it holds | Why this store |
| --- | --- | --- |
| **Neo4j Aura** (graph + vectors) | Text chunks with their meaning vectors, the business entities (accounts, deals, bids, contracts, programmes, people, partners) and the links between them | Search by meaning and follow links in one database, with no separate vector database to keep in sync |
| **SQLite** (`data/iq.db`) | Every Excel/CSV sheet as a table, the document register, users, sessions, login audit, question history with traces | Exact numbers come from SQL, never from the AI |
| **File folder** (`data/raw/`) | The original files, one folder per document and version | "Open source" returns the exact file people cited |

When someone asks a question, permission checks run first, then up to three searches run side by side. The AI writes only from their results, citing every claim, and every number is checked. Current load: 102 documents, 1,299 chunks, about 200 entities, 76 SQLite tables.

## 2. How a file is stored (loading)

```
Source file ──► Loader ──┬──► Neo4j: Document → Chunks (text + 384-number vector + tags) → MENTIONS → entities
                         ├──► SQLite: one table per sheet/CSV, fixed-name views, document register
                         └──► Folder: data/raw/<doc id>/<checksum>/<original file>
```

**Steps for every file**

1. **Read** it with the reader for its type (.docx, .pdf, .pptx, .xlsx, .csv, .json, .txt).
2. **Identify** it: the ID is `DOC-` plus a hash of its path. A SHA-256 fingerprint of the content is taken too; changed content becomes a new version folder.
3. **Keep the original** in `data/raw/<doc id>/<fingerprint>/`.
4. **Classify** it. These are rules, not AI:
   - **Area (IQ)** comes from the top folder: `GTM/`, `Campaign/`, `Accounts/`, `Sales_Revenue/`, `Solutions/`, `Channels_Partners/`, `Delivery/`.
   - **Sensitivity** comes from the file's category property. If there is none, it comes from the words RESTRICTED, CONFIDENTIAL, INTERNAL or PUBLIC in the first ~3,000 characters. If those are missing too, path rules apply (emails, transcripts, funding files and contacts are Confidential; HR is Restricted). Otherwise it is Internal.
5. **Extract** text by heading, slide or page. Excel and CSV sheets become tables: the header is the first row with 3 or more text cells, followed by data.
6. **Find what it is about.** IDs (`OPP-24101`), account names and short names ("Northwind"), partner names and contact names are matched against the entity list. Each match becomes a `MENTIONS` link. A document about 3 accounts or fewer locks every chunk to those accounts.
7. **Chunk and embed.** Text is cut into chunks of at most 1,400 characters with 150 characters of overlap. Each chunk becomes 384 numbers using `bge-small-en-v1.5`, run locally, so no text leaves the machine at this step.
8. **Write** the Document and Chunk nodes to Neo4j with tags `iq`, `classification` and `accounts`. A vector index (`chunk_embedding`) and a full-text index (`chunk_text`) cover the chunks.
9. **Register** the document in SQLite's `documents` table: ID, title, IQ, label, fingerprint, path and chunk count.

**Example: a Word file.** `Northwind_QBR_Q3_2026_Meeting_Notes.docx` (Delivery, Confidential) becomes:

- a file copy in `data/raw/test_documents/DOC-a38221fd65/43f61f4620db/`;
- one register row in SQLite;
- 6 Chunk nodes in Neo4j (Introduction, Delivery review, Client feedback, and so on), all tagged `accounts: [ACC-1001]`.

The "Client feedback" chunk links to Northwind and to the Loyalty Analytics deal (OPP-24102).

**Example: an Excel tracker.** `FocusNet_Pipeline_Report_2026-10-06.xlsx` becomes:

- a SQLite table per sheet, with the view `v_pipeline` pointing at Open Pipeline (20 deals);
- a graph node per row, for example `(OPP-24101, TCV 4.2M) -FOR_ACCOUNT-> (Northwind)`, with contract CTR-7020 `RENEWED_BY` it;
- the rows as text chunks, so they can also be found by meaning.

## 3. How a user signs in

1. The password is checked against a salted scrypt hash in SQLite's `users` table. Five wrong attempts lock the user for 10 minutes, and every attempt is written to `login_audit`.
2. A random session token goes into an HttpOnly cookie that lasts 12 hours. Only its SHA-256 is stored, in `sessions`.
3. Each request builds the user's **access list**. Each of the 7 IQs is **full**, **own** (the user's accounts or partners only), **totals only** or **none**. Margin is visible to Finance only, and the admin has no business data.

## 4. How a question is answered

Example: Priya Raman (owns Northwind) asks *"Why is the Northwind renewal at risk?"* The answer was verified in 5.5 seconds.

| Step | Agent | Reads | What happens (real numbers from this run) |
| --- | --- | --- | --- |
| 1 | Permissions | SQLite `users` | Solutions IQ in full; the other 6 IQs only for ACC-1001 and ACC-1002 |
| 2 | Entity resolver | Neo4j names | "Northwind" is matched to Account ACC-1001 by exact name or ID (no AI). Accounts the user may not see are dropped |
| 3 | Router | (none) | Keyword rules decide what runs (see below) |
| 4 | Graph agent | Neo4j graph | Walks 2 hops from ACC-1001: 19 records (deals, contract, programme, people) |
| 5 | Document agent | Neo4j vectors + keywords | 60 chunks by meaning, 40 by keyword and 40 linked to Northwind give 72 candidates. The permission filter removes 20, and the best 8 are kept from 6 documents |
| 6 | Facts agent | SQLite views | Fixed SQL on `v_pipeline` (3 open deals) and `v_renewals` (1 renewal), filtered to ACC-1001 |
| 7 | Composer | Gemini | Writes only from the 11 evidence items and cites each one ([C1] to [C11]) |
| 8 | Verifier | the evidence | Every figure and citation is checked: 5 of 5 found |

**How the router decides.** These are rules, not AI:

- **Graph agent:** runs only if a name or ID was found in step 2. A graph walk needs a starting node.
- **Document agent:** always runs, because the "why" lives in documents.
- **Facts agent:** runs only if a topic keyword matches and the user has access to that topic's IQ:
  - revenue / margin → `v_revenue`
  - deal / stalled / pipeline → `v_pipeline`
  - renewal / contract → `v_renewals`
  - bid / RFP / win rate → `v_bids`
  - funding / ECIF / MDF → `v_funding`
  - health / CSAT → `v_health`
  - project / EAC → `v_projects`
  - campaign / lead → campaign views
  - who / sponsor → `v_contacts`

**Where the semantic search runs.** Python turns the question into 384 numbers with the same local model. Neo4j's vector index then finds the chunks with the closest numbers (cosine similarity). The full-text index finds exact words and IDs, and `MENTIONS` links find chunks about the named entity. The three lists are merged by rank, so a chunk found by several searches rises. At most 2 chunks are taken per document.

**How access is enforced.** The filter is inside each database query, so the AI never receives text the user may not see:

```cypher
WHERE c.iq IN $full OR (c.iq IN $own AND all(x IN c.accounts WHERE x IN $own_accounts))
```

SQL uses `WHERE account_id IN (<user's accounts>)`. Marcus Bell, who does not own Northwind, asked the same question and got:

- Northwind's name only, with 18 linked records hidden;
- 2 chunks, because 70 of 72 candidates were removed;
- no Northwind SQL rows;
- a 403 when opening the account plan file.

For a numbers question such as *"Northwind revenue in 2026?"*, the figure comes from `SELECT year, SUM(revenue_usd) FROM v_revenue WHERE account_id='ACC-1001' GROUP BY year`. The verifier then confirms the same figure appears in the answer.

## 5. Why this design

- **One store** holds meaning and links, so there is no sync job.
- **Three merged searches**: meaning finds paraphrases, keywords find exact IDs, and graph links find related text in other words.
- **Figures** come from SQL and are checked.
- **Restricted text** never reaches the AI.
- **Every answer** is saved with citations, the reasons for each step, its queries and timings.
- **Cost stays low**: embeddings run locally, and only about 3,200 tokens go to the model per question.

## 6. Known gaps and next steps

| Gap today | Next step |
| --- | --- |
| No upload in the UI; rule-only classification; no personal-data (GDPR) check | Upload screen, limited to areas the user can access. A local personal-data scan (e.g. Microsoft Presidio) plus an in-tenant AI suggestion from the title, path and first 2 pages. Unclear or sensitive files wait in an admin review queue |
| The sensitivity label does not control access yet | Restricted and personal-data chunks for cleared roles only; emails and phones masked for others |
| No minimum relevance score, so the best 8 return even when weak | Score cut-off or a reranker; when an account is named, keep only chunks linked to it |
| Keyword routing misses other wording ("turnover"); a new Excel tracker is not used by SQL until mapped | Wider word lists or a small AI classifier as a fallback; map new trackers or detect their type automatically |
| Full reload each time; roles in code; SQLite and a local folder | Incremental loading by fingerprint; an admin page for users and roles (Entra ID groups and SharePoint permissions in production); PostgreSQL and Azure Blob, which changes only the storage layer |
