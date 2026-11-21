# Campus Hub — Diagram Pack and Django App Inventory

**Version** 1.0 · **Date** 16 November 2026

Companion to `Campus-Hub-Architecture-Spec.md` (Parts VI and VIII) and `schema.sql`.
Where a diagram and `schema.sql` disagree, `schema.sql` is correct.

## How to read the diagrams

| Convention | Meaning |
|---|---|
| One ERD per bounded context | Mermaid `erDiagram` has no subgraphs, so grouping is expressed by splitting the model into five context diagrams plus one overview. A giant single ERD is technically complete and practically unreadable |
| `PK` / `FK` / `UK` | Primary key, foreign key, unique key. Where a key is scoped ("unique per tenant") the comment says so |
| Type names | Real PostgreSQL types (`uuid`, `text`, `timestamptz`, `bigint`, `jsonb`, `tsvector`, `char3`) |
| 🔒 in a caption | Every table in that diagram has `ENABLE` + `FORCE ROW LEVEL SECURITY` except the registry/reference tables named in the caption |
| Cross-context boxes without attributes | The entity is defined in another diagram; here it is only an FK target |
| Composite FK | Written in text as `(child_col, university_id) → parent(id, university_id)`. This is the mechanism that makes a cross-tenant reference impossible |

**Validation.** All diagrams were syntax-checked by a custom linter (balanced blocks, valid
cardinality tokens, every attribute line well formed, entity names consistent); they were not
rendered, because no Mermaid renderer was available offline. Rendering is deterministic from
valid syntax, but treat the first GitHub/IDE render as the visual check.

---

# Part 1 — Database Architecture

## 1.1 D1 · Overview: the whole model in one page

Relationship map only — no columns. Read it as "what owns what"; the five context diagrams
below carry the attributes.

```mermaid
erDiagram
    UNIVERSITY ||--o{ EMAIL_DOMAIN : "claims"
    UNIVERSITY |o--o{ USER : "enrols (nullable: platform staff)"
    UNIVERSITY ||--o{ CLUB : "charters"
    UNIVERSITY ||--o{ BUSINESS : "hosts"
    UNIVERSITY ||--o{ EVENT : "scopes"
    UNIVERSITY ||--o{ MEDIA_FILE : "owns"
    UNIVERSITY ||--o{ MODERATION_REPORT : "queues"
    UNIVERSITY |o--o{ AUDIT_LOG : "tenant (no FK)"
    UNIVERSITY |o--o{ ROLE_ASSIGNMENT : "scopes delegated roles"

    USER ||--o{ ROLE_ASSIGNMENT : "holds"
    USER ||--o{ EMAIL_TOKEN : "receives"
    USER ||--o{ UNIVERSITY_TRANSFER : "requests"
    USER ||--o{ CLUB_MEMBERSHIP : "joins"
    USER ||--o{ BUSINESS : "owns (max 1 live)"
    USER ||--o{ CART : "has (max 1 active)"
    USER ||--o{ ORDER : "buys"
    USER ||--o{ NOTIFICATION : "receives"
    USER ||--o{ MEDIA_FILE : "uploads"

    CLUB ||--o{ CLUB_MEMBERSHIP : "admits"
    CLUB |o--o{ EVENT : "publishes (NULL = university-wide)"

    BUSINESS ||--o{ LISTING : "offers"
    BUSINESS ||--o{ ORDER : "fulfils"

    LISTING ||--o{ LISTING_IMAGE : "illustrated by"
    LISTING ||--o{ CART_ITEM : "added as"
    LISTING |o--o{ ORDER_ITEM : "referenced (nullable)"

    CART ||--o{ CART_ITEM : "contains"
    CART |o--o{ CHECKOUT : "converted by"
    CHECKOUT ||--o{ ORDER : "splits into (1 per seller)"
    ORDER ||--o{ ORDER_ITEM : "records"
    ORDER ||--o{ ORDER_STATUS_EVENT : "logs"

    CATEGORY |o--o{ CLUB : "classifies"
    CATEGORY |o--o{ LISTING : "classifies"
    MODERATION_REPORT }o--o| CLUB : "may target (1 of 6)"
```

Three things to notice:

1. **Everything hangs off `UNIVERSITY`** except reference data. That is the tenant boundary,
   drawn once.
2. **`CHECKOUT` sits between `CART` and `ORDER`** because a checkout is the atomic conversion
   event and the idempotency anchor; orders are its children, one per seller.
3. **`MODERATION_REPORT` has six nullable target FKs** (club, event, business, listing, user,
   order) of which exactly one is non-null — only one is drawn to keep the map legible.

## 1.2 D2 · Identity, tenancy and reference data

🔒 RLS on `USER`, `ROLE_ASSIGNMENT`, `EMAIL_TOKEN`, `UNIVERSITY_TRANSFER`.
No RLS by design on `UNIVERSITY` and `EMAIL_DOMAIN` (registry: registration must resolve a
domain to a tenant before any identity exists) and on `CATEGORY` (global reference data).

```mermaid
erDiagram
    UNIVERSITY ||--o{ EMAIL_DOMAIN : "claims"
    UNIVERSITY |o--o{ USER : "enrols (nullable: platform staff)"
    USER ||--o{ ROLE_ASSIGNMENT : "holds"
    UNIVERSITY |o--o{ ROLE_ASSIGNMENT : "scopes"
    USER ||--o{ EMAIL_TOKEN : "receives"
    USER ||--o{ UNIVERSITY_TRANSFER : "requests"
    UNIVERSITY ||--o{ UNIVERSITY_TRANSFER : "from / to"
    CATEGORY |o--o{ CATEGORY : "parent of"

    UNIVERSITY {
        uuid id PK "uuidv7()"
        text slug UK "public URL segment"
        text name
        text short_name
        char2 country_code "ISO 3166-1"
        text timezone "IANA"
        char3 default_currency "one per tenant"
        text status "onboarding|active|suspended|archived"
        jsonb settings "branding, feature flags"
        timestamptz created_at
        timestamptz updated_at
    }

    EMAIL_DOMAIN {
        uuid id PK
        uuid university_id FK
        text domain UK "globally unique, lower case"
        bool is_active
        timestamptz verified_at "nullable"
        timestamptz created_at
    }

    USER {
        uuid id PK
        text email UK "lower case, login identifier"
        text password "argon2 hash"
        text full_name
        uuid university_id FK "nullable: platform staff only"
        text status "pending|active|suspended|deleted"
        bool platform_staff "derived from grants"
        timestamptz email_verified_at
        int auth_version "bumped to kill sessions"
        bool is_active
        bool is_superuser
        timestamptz last_login
        timestamptz date_joined
        timestamptz deleted_at "anonymised, never removed"
    }

    ROLE_ASSIGNMENT {
        uuid id PK
        uuid user_id FK
        text role "platform_admin|university_admin|university_moderator"
        uuid university_id FK "NULL for platform_admin"
        uuid granted_by_id FK
        timestamptz granted_at
        timestamptz revoked_at "nullable"
        uuid revoked_by_id FK
    }

    EMAIL_TOKEN {
        uuid id PK
        uuid user_id FK
        uuid university_id FK "nullable"
        text purpose "verify_email|change_email|university_transfer"
        text email "address the token was sent to"
        bytea token_hash UK "sha256, raw token never stored"
        timestamptz expires_at
        timestamptz consumed_at "nullable"
        smallint attempts
        timestamptz created_at
    }

    UNIVERSITY_TRANSFER {
        uuid id PK
        uuid user_id FK
        uuid from_university_id FK
        uuid to_university_id FK
        text status "requested|approved|rejected|cancelled"
        text note
        timestamptz requested_at
        timestamptz decided_at
        uuid decided_by_id FK
    }

    CATEGORY {
        uuid id PK
        text domain "club|listing"
        text slug
        text name
        uuid parent_id FK "nullable, same domain only"
        integer sort_order
        bool is_active
    }
```

**Key invariants**

| Invariant | Mechanism |
|---|---|
| A user has exactly one university at a time | `USER.university_id` is a single column; `UNIQUE (id, university_id)` is the anchor for every composite FK |
| A domain maps to exactly one university | `EMAIL_DOMAIN.domain` is globally `UNIQUE` |
| One live grant per (user, role, scope) | Partial unique index on `(user_id, role, university_id) NULLS NOT DISTINCT WHERE revoked_at IS NULL` |
| A platform admin has no tenant; a tenant role must have one | `role_assignment_scope_check` |
| An active account must have a tenant unless it is platform staff | `user_active_scope_check` |
| Verification tokens are single-use and hashed | `token_hash` unique + `consumed_at` + 24 h expiry |
| A transfer never moves a user to the same tenant | `from_university_id <> to_university_id` |

## 1.3 D3 · Event Hub

🔒 All three tables RLS-enabled. `CLUB.slug` and `EVENT.slug` are unique **per tenant**.

```mermaid
erDiagram
    UNIVERSITY ||--o{ CLUB : "charters"
    CATEGORY |o--o{ CLUB : "classifies"
    USER ||--o{ CLUB_MEMBERSHIP : "joins"
    CLUB ||--o{ CLUB_MEMBERSHIP : "admits"
    CLUB |o--o{ EVENT : "publishes (NULL = university-wide)"
    UNIVERSITY ||--o{ EVENT : "scopes"
    MEDIA_FILE |o--o{ CLUB : "logo + cover"
    MEDIA_FILE |o--o{ EVENT : "cover"

    CLUB {
        uuid id PK
        uuid university_id FK "tenant, immutable"
        text slug UK "unique per university"
        text name
        text summary
        text description
        uuid category_id FK "nullable"
        uuid logo_file_id FK "nullable"
        uuid cover_file_id FK "nullable"
        text status "draft|pending|approved|rejected|suspended|archived"
        text join_policy "open|request"
        uuid created_by_id FK "founder"
        timestamptz submitted_at
        uuid reviewed_by_id FK "nullable"
        timestamptz reviewed_at
        text review_note
        timestamptz suspended_at
        uuid suspended_by_id FK
        text suspension_reason
        timestamptz created_at
        timestamptz updated_at
    }

    CLUB_MEMBERSHIP {
        uuid id PK
        uuid university_id FK "repeated to enable both composite FKs"
        uuid club_id FK
        uuid user_id FK
        text role "member|admin"
        text status "invited|requested|active|left|removed|rejected"
        timestamptz requested_at
        timestamptz decided_at
        uuid decided_by_id FK
        text note
        timestamptz created_at
        timestamptz updated_at
    }

    EVENT {
        uuid id PK
        uuid university_id FK
        uuid club_id FK "NULL = university-wide event"
        text title
        text slug UK "unique per university"
        text summary
        text description
        uuid cover_file_id FK "nullable"
        timestamptz starts_at
        timestamptz ends_at
        text timezone "IANA, wall-clock rendering"
        text venue_name
        text venue_address
        bool is_online
        text online_url
        integer capacity "informational until RSVP exists"
        text visibility "public|university"
        text status "draft|published|cancelled|completed|archived"
        uuid created_by_id FK
        timestamptz published_at
        timestamptz cancelled_at
        text cancellation_reason
        timestamptz created_at
        timestamptz updated_at
    }
```

**Why the membership table carries `university_id` twice over:** it is the pivot that lets the
row hold `(club_id, university_id) → clubs_club(id, university_id)` **and**
`(user_id, university_id) → accounts_user(id, university_id)` at the same time. Because both
FKs share one column, a member from another university is not "rejected" — the row cannot be
inserted at all.

**Invariants and where they live**

| Invariant | Mechanism |
|---|---|
| A club's members belong to the club's university | Two composite FKs on `CLUB_MEMBERSHIP` |
| One row per (club, user) — re-joining reuses it | `UNIQUE (club_id, user_id)` |
| Only approved clubs publish events | Trigger T1 `event_publisher_approved` + service guard |
| An approved club keeps an active admin | Deferred constraint trigger T2 (checked at COMMIT) |
| An event cannot belong to a foreign club or a foreign creator | Composite FKs on `EVENT` |
| An event ends after it starts; an in-person event has a venue | `event_time_check`, `event_location_check` |
| Cancelled means timestamped | `event_cancelled_check` |

## 1.4 D4 · Marketplace catalogue and cart

🔒 All five tables RLS-enabled. Note the deliberate separation: the **cart** is buyer-owned and
mutable; the **catalogue** is seller-owned. They meet only at `LISTING`.

```mermaid
erDiagram
    UNIVERSITY ||--o{ BUSINESS : "hosts"
    USER ||--o{ BUSINESS : "owns (max 1 live)"
    BUSINESS ||--o{ LISTING : "offers"
    CATEGORY |o--o{ LISTING : "classifies"
    LISTING ||--o{ LISTING_IMAGE : "illustrated by"
    MEDIA_FILE ||--o{ LISTING_IMAGE : "stored as"
    MEDIA_FILE |o--o{ BUSINESS : "logo"
    USER ||--o{ CART : "has (max 1 active)"
    CART ||--o{ CART_ITEM : "contains"
    LISTING ||--o{ CART_ITEM : "added as"

    BUSINESS {
        uuid id PK
        uuid university_id FK "= owner's university, enforced"
        uuid owner_id FK
        text slug UK "unique per university"
        text name
        text description
        uuid logo_file_id FK "nullable"
        text contact_email
        text contact_phone
        bigint delivery_fee_minor "flat fee, 0 = none"
        text status "active|suspended|closed"
        timestamptz suspended_at
        uuid suspended_by_id FK
        text suspension_reason
        timestamptz created_at
        timestamptz updated_at
    }

    LISTING {
        uuid id PK
        uuid university_id FK
        uuid business_id FK
        uuid category_id FK "nullable"
        text kind "product|service"
        text title
        text slug UK "unique per business"
        text description
        bigint price_minor "tenant currency, minor units"
        integer stock_on_hand "NULL = unlimited"
        text status "draft|active|paused|archived"
        integer version "optimistic concurrency"
        timestamptz published_at
        timestamptz archived_at
        tsvector search_vector "generated, GIN indexed"
        timestamptz created_at
        timestamptz updated_at
    }

    LISTING_IMAGE {
        uuid id PK
        uuid university_id FK
        uuid listing_id FK
        uuid file_id FK
        smallint position "0-7, deferrable unique"
        text alt_text
        timestamptz created_at
    }

    CART {
        uuid id PK
        uuid university_id FK
        uuid user_id FK
        text status "active|ordered|abandoned"
        timestamptz created_at
        timestamptz updated_at
    }

    CART_ITEM {
        uuid id PK
        uuid university_id FK
        uuid cart_id FK
        uuid listing_id FK
        integer quantity "1-100"
        bigint price_at_add_minor "display only, never charged"
        timestamptz created_at
        timestamptz updated_at
    }
```

**Invariants and where they live**

| Invariant | Mechanism |
|---|---|
| A business's university is its owner's university | `business_owner_fk (owner_id, university_id)` |
| One live business per student | Partial unique `(owner_id) WHERE status <> 'closed'` |
| A listing belongs to a business in the same university | `listing_business_fk (business_id, university_id)` |
| A product declares stock; a service may not | `listing_stock_required_check` |
| Sold-out is derived, never stored | `stock_on_hand = 0`, no `sold_out` status |
| One active cart per user | Partial unique `(user_id) WHERE status='active'` |
| One line per listing per cart (quantity aggregates) | `UNIQUE (cart_id, listing_id)` |
| A cart line cannot reference a foreign listing | `cart_item_listing_fk (listing_id, university_id)` |

## 1.5 D5 · Checkout and orders

🔒 All four tables RLS-enabled; the application role has **no DELETE** on any of them
(append-only financial history).

```mermaid
erDiagram
    CART |o--o{ CHECKOUT : "converted by (at most once)"
    USER ||--o{ CHECKOUT : "places"
    CHECKOUT ||--o{ ORDER : "splits into, 1 per seller"
    BUSINESS ||--o{ ORDER : "fulfils"
    USER ||--o{ ORDER : "buys"
    ORDER ||--o{ ORDER_ITEM : "records"
    ORDER ||--o{ ORDER_STATUS_EVENT : "logs every transition"
    LISTING |o--o{ ORDER_ITEM : "nullable reference"

    CHECKOUT {
        uuid id PK
        uuid university_id FK
        uuid buyer_id FK
        uuid cart_id FK
        text idempotency_key "client Idempotency-Key"
        bytea request_fingerprint "sha256 of normalised body"
        text status "pending|committed|failed"
        bigint total_minor "sum of order totals"
        timestamptz created_at
        timestamptz committed_at
    }

    ORDER {
        uuid id PK
        uuid university_id FK
        uuid checkout_id FK
        uuid business_id FK
        uuid buyer_id FK
        text order_number UK "human ref, unique per tenant"
        text status "pending|accepted|ready|completed|cancelled"
        text payment_method "cash_on_collection|mobile_money|bank_transfer"
        text payment_status "unpaid|paid|refunded|failed"
        text fulfilment_method "pickup|delivery"
        text delivery_address "required when delivery"
        bigint subtotal_minor
        bigint delivery_fee_minor
        bigint total_minor "= subtotal + fee, CHECK"
        char3 currency "snapshot of tenant currency"
        text buyer_note
        text seller_note
        timestamptz placed_at
        timestamptz accepted_at
        timestamptz ready_at
        timestamptz completed_at
        timestamptz cancelled_at
        uuid cancelled_by_id FK
        text cancellation_reason
        integer version "optimistic concurrency"
    }

    ORDER_ITEM {
        uuid id PK
        uuid university_id FK
        uuid order_id FK
        uuid listing_id FK "nullable: history survives deletion"
        text listing_kind "product|service"
        text title_snapshot "copied at purchase"
        bigint unit_price_minor "copied at purchase"
        integer quantity
        bigint line_total_minor "= unit x qty, CHECK"
        jsonb snapshot "image key, excerpt, category"
    }

    ORDER_STATUS_EVENT {
        uuid id PK
        uuid university_id FK
        uuid order_id FK
        text from_status "NULL for the first event"
        text to_status
        uuid actor_id FK "nullable: system transitions"
        text note
        timestamptz created_at
    }
```

**Invariants and where they live**

| Invariant | Mechanism |
|---|---|
| A cart converts at most once, even with a new idempotency key | Partial unique `(cart_id) WHERE status='committed'` |
| The same key with a different body is refused | `UNIQUE (university_id, buyer_id, idempotency_key)` + fingerprint comparison |
| One order per seller per checkout | `UNIQUE (checkout_id, business_id)` |
| Totals add up | `CHECK (total_minor = subtotal_minor + delivery_fee_minor)` |
| A delivery order has an address | `order_delivery_address_check` |
| An order cannot reference a foreign buyer, business or checkout | Three composite FKs |
| History survives a deleted listing | `ON DELETE SET NULL (listing_id)` + snapshot columns |
| Every transition is attributable | `orders_order_status_event` written in the same transaction |

## 1.6 D6 · Platform services: media, moderation, notifications, audit

🔒 All four RLS-enabled. `AUDIT_LOG` is append-only at the grant level (`INSERT, SELECT` only)
and intentionally has **no foreign keys** — an audit row must outlive the actor and the object.

```mermaid
erDiagram
    UNIVERSITY ||--o{ MEDIA_FILE : "owns"
    USER ||--o{ MEDIA_FILE : "uploads"
    UNIVERSITY ||--o{ MODERATION_REPORT : "queues"
    USER |o--o{ MODERATION_REPORT : "reports"
    USER |o--o{ MODERATION_REPORT : "resolves"
    MODERATION_REPORT }o--o| CLUB : "targets (1 of 6)"
    MODERATION_REPORT }o--o| EVENT : "targets (1 of 6)"
    MODERATION_REPORT }o--o| BUSINESS : "targets (1 of 6)"
    MODERATION_REPORT }o--o| LISTING : "targets (1 of 6)"
    MODERATION_REPORT }o--o| ORDER : "targets (1 of 6)"
    USER ||--o{ NOTIFICATION : "receives"
    UNIVERSITY |o--o{ AUDIT_LOG : "scopes, no FK"

    MEDIA_FILE {
        uuid id PK
        uuid university_id FK
        uuid uploaded_by_id FK "tenant matches uploader"
        text purpose "avatar|university_logo|club_logo|club_cover|event_cover|business_logo|listing_image|report_evidence"
        text storage_key UK "server-generated object key"
        text original_filename "metadata only"
        text content_type "sniffed, not trusted"
        bigint byte_size "max 10 MiB"
        bytea checksum_sha256
        integer width
        integer height
        text status "pending|ready|quarantined|deleted"
        text visibility "public|protected"
        timestamptz created_at
        timestamptz ready_at
        timestamptz deleted_at
    }

    MODERATION_REPORT {
        uuid id PK
        uuid university_id FK
        uuid reporter_id FK "nullable"
        text target_type "club|event|business|listing|user|order"
        uuid target_club_id FK "exactly one target set"
        uuid target_event_id FK
        uuid target_business_id FK
        uuid target_listing_id FK
        uuid target_user_id FK
        uuid target_order_id FK
        text reason "spam|fraud|harassment|counterfeit|inappropriate|other"
        text details
        text status "open|actioned|dismissed"
        uuid resolved_by_id FK
        timestamptz resolved_at
        text resolution_note
        timestamptz created_at
    }

    NOTIFICATION {
        uuid id PK
        uuid university_id FK
        uuid user_id FK
        text channel "in_app|email"
        text kind "order.placed|order.accepted|club.approved|..."
        jsonb payload "render payload, no FK to domain rows"
        text dedupe_key UK "nullable, idempotent send"
        text status "pending|sent|failed|cancelled"
        timestamptz scheduled_at
        timestamptz created_at
        timestamptz sent_at
        timestamptz read_at
        smallint attempts
        text last_error
    }

    AUDIT_LOG {
        uuid id PK
        timestamptz occurred_at
        uuid university_id "no FK, nullable"
        uuid actor_id "no FK, survives anonymisation"
        text actor_kind "user|system|platform_admin|university_admin|club_admin|business_owner"
        text action "domain.verb, e.g. club.approved"
        text target_type
        uuid target_id
        text request_id
        inet ip
        jsonb data "redacted before/after diff"
    }
```

**Why the moderation target is five columns instead of one `target_id`:** a polymorphic
`(target_type, target_id)` pair cannot be a foreign key, cannot be joined, and must be
re-validated in every consumer. Five nullable columns plus `num_nonnulls(...) = 1` and
`report_target_matches_type` give real referential integrity and a composite tenant FK per
target.

## 1.7 Table → context → isolation map

| Table | Context | Tenant column | RLS |
|---|---|---|---|
| `universities_university` | D2 registry | *is* the tenant | no (registry) |
| `universities_email_domain` | D2 registry | `university_id` | no (registry, documented) |
| `taxonomy_category` | D2 reference | — | no (global reference) |
| `accounts_user` | D2 identity | `university_id` (nullable) | 🔒 |
| `accounts_role_assignment` | D2 identity | `university_id` (nullable) | 🔒 |
| `accounts_email_token` | D2 identity | `university_id` (nullable) | 🔒 |
| `accounts_university_transfer` | D2 identity | `from_` / `to_university_id` | 🔒 |
| `clubs_club` | D3 event hub | `university_id` | 🔒 |
| `clubs_membership` | D3 event hub | `university_id` | 🔒 |
| `events_event` | D3 event hub | `university_id` | 🔒 |
| `businesses_business` | D4 catalogue | `university_id` | 🔒 |
| `marketplace_listing` | D4 catalogue | `university_id` | 🔒 |
| `marketplace_listing_image` | D4 catalogue | `university_id` | 🔒 |
| `cart_cart` | D4 cart | `university_id` | 🔒 |
| `cart_cart_item` | D4 cart | `university_id` | 🔒 |
| `orders_checkout` | D5 orders | `university_id` | 🔒 |
| `orders_order` | D5 orders | `university_id` | 🔒 |
| `orders_order_item` | D5 orders | `university_id` | 🔒 |
| `orders_order_status_event` | D5 orders | `university_id` | 🔒 |
| `media_file` | D6 platform | `university_id` | 🔒 |
| `moderation_report` | D6 platform | `university_id` | 🔒 |
| `notifications_notification` | D6 platform | `university_id` | 🔒 |
| `audit_log` | D6 platform | `university_id` (nullable) | 🔒 |

23 tables · 20 RLS-enabled · 3 deliberate registry/reference exceptions, each argued in
Part V §5.5 of the specification.

---

# Part 2 — Backend Architecture

## 2.1 B1 · Layered components

```mermaid
flowchart TB
    subgraph CL["Clients"]
        SPA["Web SPA<br/>first-party, same origin"]
        ANON["Public visitor<br/>event pages"]
    end

    subgraph EDGE["Edge"]
        TLS["TLS termination<br/>HSTS · secure cookies"]
        CDN["CDN<br/>object-storage domain"]
    end

    subgraph IFACE["Interface layer — Django request"]
        MW["TenantMiddleware<br/>authenticate · auth_version<br/>atomic + SET LOCAL"]
        VIEW["DRF ViewSets<br/>explicit serializers"]
        ERRH["problem+json<br/>exception handler"]
    end

    subgraph APPLAYER["Application layer"]
        POL["policies.py<br/>pure decision functions"]
        SVC["services.py<br/>transaction owners"]
        SEL["selectors.py<br/>read composition"]
    end

    subgraph DATAACC["Data access"]
        MGR["TenantScopedManager<br/>fail-closed"]
        ORM["Django ORM"]
    end

    subgraph STATE["State"]
        PG[("PostgreSQL 18<br/>RLS forced · composite FKs")]
        OBJ[("Object storage<br/>private bucket")]
        CACHE[("Cache table<br/>sessions · throttles")]
    end

    subgraph ASYNC["Asynchronous"]
        WRK["Outbox worker<br/>SKIP LOCKED"]
        CRON["Nightly commands<br/>expire · sweep · invariants"]
        MAIL["Email provider"]
    end

    SPA --> TLS
    ANON --> TLS
    ANON --> CDN
    SPA -.->|"public images"| CDN
    TLS --> MW
    MW --> VIEW
    VIEW --> ERRH
    VIEW --> POL
    VIEW --> SEL
    POL --> SVC
    SVC --> ORM
    SEL --> MGR
    MGR --> ORM
    ORM --> PG
    CACHE --- PG
    VIEW -->|"presigned read"| OBJ
    SVC -->|"write object"| OBJ
    CDN --> OBJ
    WRK --> PG
    WRK --> MAIL
    CRON --> PG
```

**Layer rules, in one line each**

| Layer | May | Must not |
|---|---|---|
| Interface | Parse HTTP, choose a serializer, call a policy or service | Contain business rules, open transactions, or query another app's models |
| Policy | Decide with data already loaded | Write, or issue more than a trivial lookup |
| Service | Own the transaction, enforce invariants, write audit + outbox | Speak HTTP, return `Http404`, commit another app's transaction |
| Selector | Compose a read queryset for one caller | Bypass the tenant manager |
| Data access | Fail closed on a missing tenant | Silently fall back to `all()` |

## 2.2 B2 · Django app dependency graph

Arrows point from a dependent app to the app it depends on. To keep the graph readable, two
edges that every app has are omitted: **everything depends on `core`**, and **every
tenant-owning app depends on `universities`**. Both are listed explicitly in §3.1.

```mermaid
flowchart TD
    subgraph L0["Layer 0 · foundation, no tables"]
        CORE["core"]
    end

    subgraph L1["Layer 1 · registry and reference"]
        UNI["universities"]
        TAX["taxonomy"]
    end

    subgraph L2["Layer 2 · identity"]
        ACC["accounts"]
    end

    subgraph L3["Layer 3 · media"]
        MED["media"]
    end

    subgraph L4["Layer 4 · product domains"]
        CLB["clubs"]
        EVT["events"]
        BUS["businesses"]
        MKT["marketplace"]
    end

    subgraph L5["Layer 5 · transaction"]
        CRT["cart"]
        ORD["orders"]
    end

    subgraph L6["Layer 6 · cross-cutting"]
        MOD["moderation"]
        NOT["notifications"]
        AUD["audit"]
    end

    TAX --> CORE
    UNI --> CORE
    ACC --> UNI
    MED --> ACC
    CLB --> ACC
    CLB --> MED
    CLB --> TAX
    EVT --> CLB
    EVT --> MED
    BUS --> ACC
    BUS --> MED
    MKT --> BUS
    MKT --> MED
    MKT --> TAX
    CRT --> MKT
    ORD --> CRT
    ORD --> BUS
    MOD --> CLB
    MOD --> EVT
    MOD --> MKT
    MOD --> ORD
    NOT --> ACC
    AUD --> CORE
```

**Prohibited edges** (enforced by `import-linter` in CI, not by convention):

| Prohibited | Why |
|---|---|
| `core` → any domain app | It is the bottom of the graph; one import makes everything circular |
| `accounts` → `clubs` / `marketplace` / `orders` | Identity must not know about content |
| `media` → any entity app | Media owns files, not the things they illustrate |
| any app → `moderation` | Moderation reacts; if domains import it, they couple to reports |
| `audit` → any domain app | Audit takes primitives (`target_type`, `target_id`), never model classes |
| `*/api/*` → `all_objects` | The escape hatch must never reach the request path |
| `*/services.py` → `rest_framework` | Services must be usable from workers and commands |

## 2.3 B3 · Runtime topology (MVP)

```mermaid
flowchart LR
    U["Students, club admins,<br/>business owners, admins"]
    V["Public visitors"]

    U --> LB["TLS / load balancer"]
    V --> LB
    V --> CDN["CDN"]
    CDN --> R2[("Object storage<br/>private bucket")]

    subgraph APP["Application image"]
        WEB["web · gunicorn 3 workers<br/>role campus_app"]
        WRK["worker · run_outbox_worker<br/>role campus_ops"]
    end

    LB --> WEB
    WEB --> PG[("PostgreSQL 18<br/>owner / app / ops roles")]
    WEB -->|"ops alias:<br/>login lookup, platform API"| PG
    WEB --> R2
    WRK --> PG
    WRK --> MAIL["Email provider"]
    CRON["Nightly cron<br/>3 management commands"] --> PG
    WEB --> SENTRY["Sentry"]
    MON["Uptime monitor"] -->|"/health, /health/ready"| WEB
```

Two processes, one database, one bucket, no Redis and no broker. The `ops` connection is drawn
separately because it is the only `BYPASSRLS` path and must stay visible in the architecture.

## 2.4 B4 · Write path, end to end

The diagram that explains the whole design: one request, one transaction, one tenant, one
guarded state transition, one outbox row.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant MW as TenantMiddleware
    participant V as ViewSet
    participant P as Policy
    participant S as Service
    participant DB as PostgreSQL
    participant W as Outbox worker

    C->>MW: POST /api/v1/orders/{id}/accept + session cookie + CSRF
    MW->>MW: user active? auth_version matches session?
    MW->>DB: BEGIN
    MW->>DB: SET LOCAL app.university_id = '...'
    MW->>V: dispatch
    V->>DB: SELECT order (tenant manager + RLS)
    V->>P: can_transition(actor, order)
    P-->>V: allow (owner of the business)
    V->>S: accept(order, actor)
    S->>DB: UPDATE orders_order SET status='accepted'<br/>WHERE id=? AND status='pending'

    alt rowcount = 0
        S-->>V: Conflict(order_not_pending)
        MW->>DB: ROLLBACK
        V-->>C: 409 problem+json
    else rowcount = 1
        S->>DB: INSERT orders_order_status_event
        S->>DB: INSERT notifications_notification (outbox)
        S->>DB: INSERT audit_log
        MW->>DB: COMMIT
        V-->>C: 200 order with timeline
    end

    Note over W,DB: after commit
    W->>DB: claim rows FOR UPDATE SKIP LOCKED
    W->>W: re-enter tenant_scope(row.university_id)
    W->>C: (email) order accepted
```

The two details that matter most: `SET LOCAL` is issued **after** `BEGIN` and dies with the
transaction, and the state transition is a **guarded `UPDATE`** rather than read-then-write, so
two simultaneous transitions resolve to exactly one winner.

## 2.5 Component responsibilities

| Component | Owns | Never does |
|---|---|---|
| `core.tenancy` | Tenant resolution, `SET LOCAL`, request transaction | Decide authorisation |
| `core.permissions` | Which *kind* of actor may call an endpoint | Query the object (it does not exist yet) |
| `policies.py` | Whether *this* actor may act on *this* object | Write, or open a transaction |
| `services.py` | Transactions, invariants, ordering of side effects | Speak HTTP |
| `selectors.py` | Read composition per caller | Skip the tenant filter |
| `TenantScopedManager` | Fails closed when no tenant is set | Provide a silent `all()` |
| RLS + constraints | Row visibility and structural truth | Express actor-dependent rules |
| Outbox worker | Delivery under a per-row tenant context | Read domain tables speculatively |

---

# Part 3 — Django App Inventory

Fourteen **MVP** apps, nine **post-MVP** apps. A post-MVP app is listed only if there is a
named trigger for building it — "we might need it" is not a trigger.

## 3.1 MVP apps

| # | App | Label | Phase | Owns tables | Responsibility | Depends on |
|---|---|---|---|---|---|---|
| 1 | `core` | **MVP** | 0 | — (abstract models only) | Tenant middleware and `SET LOCAL`, scoped managers, DRF base permissions, problem+json handler, pagination, idempotency helper, S3 adapter, image validation, exceptions | — |
| 2 | `universities` | **MVP** | 1 | `university`, `email_domain` | Tenant registry, institutional email domains, per-tenant settings (branding, currency, timezone), onboarding | `core` |
| 3 | `taxonomy` | **MVP** | 1 | `category` | Global two-level category tree for clubs and listings; seeded reference data | `core` |
| 4 | `accounts` | **MVP** | 1 | `user`, `role_assignment`, `email_token`, `university_transfer` | Registration, email verification, login/logout, password reset and change, delegated role grants, suspension, anonymisation, tenant transfer | `core`, `universities` |
| 5 | `media` | **MVP** | 1 | `file` | Upload validation and re-encoding, storage keys, public/protected delivery, slots and citation rules, orphan sweep | `core`, `universities`, `accounts` |
| 6 | `clubs` | **MVP** | 2 | `club`, `membership` | Club lifecycle (draft → pending → approved/rejected → suspended → archived), join policy, membership and club-level admin roles, last-admin rule | `core`, `universities`, `accounts`, `media`, `taxonomy` |
| 7 | `events` | **MVP** | 2 | `event` | Event lifecycle, publishing rules (approved clubs only), material-change audit, cancellation, discovery feed, public projection | `core`, `universities`, `accounts`, `clubs`, `media` |
| 8 | `notifications` | **MVP** | 2 | `notification` | Transactional outbox, in-app inbox, email rendering, dedupe keys, retry/backoff, `run_outbox_worker` | `core`, `universities`, `accounts` |
| 9 | `audit` | **MVP** | 1 | `audit_log` | Append-only record of privileged and financial actions; `record()` used by services; tenant-filtered reader | `core`, `universities` |
| 10 | `businesses` | **MVP** | 3 | `business` | Seller identity, one-live-business rule, suspension, delivery fee, ownership transfer (platform-only) | `core`, `universities`, `accounts`, `media` |
| 11 | `marketplace` | **MVP** | 3 | `listing`, `listing_image` | Catalogue: products and services, stock or unlimited, pricing, images, search (PostgreSQL FTS + trigram), optimistic concurrency | `core`, `universities`, `accounts`, `businesses`, `media`, `taxonomy` |
| 12 | `cart` | **MVP** | 4 | `cart`, `cart_item` | One active cart per buyer, add/merge/update/remove, availability flags, price-at-add display | `core`, `universities`, `accounts`, `marketplace` |
| 13 | `orders` | **MVP** | 4 | `checkout`, `order`, `order_item`, `order_status_event` | Checkout transaction (locks, stock decrement, snapshot, idempotency), per-seller split, order state machine, payment *status*, timeline | `core`, `universities`, `accounts`, `businesses`, `marketplace`, `cart` |
| 14 | `moderation` | **MVP** | 5 | `report` | Reports against six target types, moderation queue, resolution that delegates the remedy to the owning domain | `core`, `universities`, `accounts`, `clubs`, `events`, `marketplace`, `orders` |

**Total MVP: 14 apps · 23 tables.**

Reading the table as a build order: `core` first, then Phase 1 (registry + identity + media),
then Phase 2 (Event Hub), Phase 3 (catalogue), Phase 4 (the money path), Phase 5 (trust and
safety). That matches Part XVI of the specification.

## 3.2 Post-MVP apps

| # | App | Label | Trigger to build it | New tables | Depends on | Cost if built early |
|---|---|---|---|---|---|---|
| 1 | `payments` | **POST-MVP** | A university or seller requires in-app payment, or a university supplies its M-Pesa shortcode | `payment`, `payment_webhook_event`, `payment_reconciliation` | `core`, `orders` | High: gateway integration, reconciliation, refunds and dispute handling before there is any volume to justify them |
| 2 | `ticketing` | **POST-MVP** | A club asks to sell tickets or cap attendance | `event_rsvp`, `ticket`, `ticket_check_in` | `core`, `events`, `payments`, `notifications` | High: capacity concurrency, refunds and check-in UI; the schema's `capacity` stays informational until then |
| 3 | `billing` | **POST-MVP** | The first paid university licence or Seller Pro subscription (Part XX commercial model) | `plan`, `subscription`, `invoice`, `billing_event` | `core`, `universities`, `businesses` | Medium: invoicing and dunning for revenue that does not exist yet |
| 4 | `promotions` | **POST-MVP** | Sellers ask for visibility, or the first paid boost is sold | `promotion_campaign`, `promotion_slot`, `promotion_impression` | `core`, `marketplace` | Low-medium: ranking rules and disclosure (a paid placement must be labelled) |
| 5 | `messaging` | **POST-MVP** | Support tickets show that buyer/seller notes are insufficient — measured, not guessed | `thread`, `message`, `thread_participant` | `core`, `orders` | Medium: a second real-time-ish surface with its own moderation burden |
| 6 | `reviews` | **POST-MVP** | ≥ 100 completed orders, so a rating is statistically meaningful | `review`, `rating_summary` | `core`, `orders`, `businesses` | Medium: ratings without volume are noise and invite retaliation |
| 7 | `analytics` | **POST-MVP** | A university asks for a termly engagement report (this is also a renewal lever) | Mostly read-only views/materialised views; `report_snapshot` if exports are needed | `core` (reads everything) | Low code, high value — but it must read through the platform path, never a tenant session |
| 8 | `integrations` | **POST-MVP** | A university requires SSO (SAML/OIDC) or a roster feed for automatic verification | `identity_provider`, `roster_entry`, `sync_run` | `core`, `universities`, `accounts` | Medium-high: per-tenant configuration, certificate rotation, sync failure handling |
| 9 | `delivery` | **POST-MVP** | Orders per week exceed what sellers can hand-deliver, or a university wants campus pickup points | `delivery_zone`, `delivery_assignment`, `pickup_point` | `core`, `orders`, `businesses` | Medium: courier coordination is an operations business, not a feature |

**Total post-MVP: 9 apps · ~20 potential tables** — none of which exist in `schema.sql` today,
and none of which the MVP design blocks.

### Explicitly *not* planned as an app

| Candidate | Why not |
|---|---|
| `search` | PostgreSQL full-text + trigram is enough for tens of thousands of listings. If it stops being enough, that is an infrastructure swap (Meilisearch/Typesense) behind `marketplace.selectors`, not a new domain app |
| `api` / `common` / `utils` | An app with no owner becomes the place where boundaries go to die. Routers live in each app's `api/urls.py`; shared code lives in `core` only with a stated contract |
| `notifications_push` | Push is a channel inside `notifications` (a new `channel` value + a provider adapter), not a domain |
| `admin_panel` | Platform administration is an API surface (`/api/v1/platform/`) plus templates, not a Django app with models |
| `payments_wallet` | Holding student balances is a regulated activity, not a feature flag |

## 3.3 Rules for adding an app

1. **It must own at least one table that no other app may write.** Otherwise it is a module
   inside an existing app (`selectors.py`, `policies.py`).
2. **It enters at one layer and depends downwards only.** Add the edge to the diagram in §2.2
   and to the `import-linter` layer contract in the same pull request.
3. **One service function per use case, and it owns the transaction.** No app may call another
   app's model `.save()`.
4. **If it has a `university_id` column, it needs an RLS migration in the same release** —
   `ENABLE`, `FORCE`, one `tenant_isolation` policy, and a row in the §1.7 map.
5. **It ships with its tests**: at minimum one isolation test (TS-02 style) and one
   permission-matrix test per endpoint.
6. **Name it after the domain, not the table.** `orders`, not `order_items`; `marketplace`, not
   `listings`.

## 3.4 Counting the boundary

| Metric | MVP | With all post-MVP apps |
|---|---|---|
| Django apps | 14 | 23 |
| Tables | 23 | ~43 |
| RLS policies | 20 | ~38 |
| Deployment units | 1 image, 2 processes | unchanged |

The point of the post-MVP list is not that all nine will be built. It is that each has a named
trigger, so "should we build this now?" has an answer that is not a matter of taste — and so the
MVP schema can be reviewed against them once, rather than redesigned later.
