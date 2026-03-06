<!-- Created: 2026-03-05 -->
# Stories Tab Architecture Diagrams

> Open in VS Code with "Markdown Preview Enhanced" or "Mermaid Preview" extension to render.

## 1. Information Hierarchy

```mermaid
graph TD
    A["Stories Tab<br/>(list view)"] --> B["Parent Group Cards<br/>7~10 macro stories"]
    A --> C["Standalone Threads<br/>~61 ungrouped"]

    B --> D["Thread Detail Page<br/>/news/thread/[id]"]
    C --> D

    D --> E["Article Detail<br/>/news/[slug]"]

    style A fill:#1a1a1a,color:#fff,stroke:none
    style B fill:#3b82f6,color:#fff,stroke:none
    style C fill:#6b7280,color:#fff,stroke:none
    style D fill:#8b5cf6,color:#fff,stroke:none
    style E fill:#10b981,color:#fff,stroke:none
```

## 2. Parent Thread Data Model

```mermaid
erDiagram
    wsj_parent_threads {
        uuid id PK
        text title
        timestamptz created_at
        text status "active | archived"
    }

    wsj_story_threads {
        uuid id PK
        text title
        uuid parent_id FK "nullable"
        int member_count
        text status "active | cooling | archived"
        float[] centroid
        timestamptz first_seen
        timestamptz last_seen
    }

    wsj_items {
        uuid id PK
        text title
        uuid thread_id FK "nullable"
        text importance
        timestamptz published_at
    }

    wsj_parent_threads ||--o{ wsj_story_threads : "groups"
    wsj_story_threads ||--o{ wsj_items : "contains"
```

## 3. Parent Grouping Pipeline

```mermaid
flowchart LR
    subgraph Daily Pipeline
        A[Thread<br/>Matching] --> B[CE Merge<br/>Pass]
    end

    subgraph "Parent Grouping (new)"
        B --> C{Active threads<br/>> 10?}
        C -->|Yes| D[Collect thread<br/>titles + metadata]
        C -->|No| E[Skip]
        D --> F["LLM Grouping<br/>(Gemini Flash)"]
        F --> G[Create/Update<br/>parent_threads]
        G --> H[Set parent_id<br/>on children]
    end

    subgraph Frontend
        H --> I[getActiveThreadsGrouped]
        I --> J[Stories Tab]
        J --> K[Thread Detail Page]
    end

    style F fill:#f59e0b,color:#1a1a1a,stroke:none
    style J fill:#3b82f6,color:#fff,stroke:none
    style K fill:#8b5cf6,color:#fff,stroke:none
```

## 4. Heat Score Flow

```mermaid
flowchart TD
    A["Article importance<br/>(must_read=3, worth_reading=2, optional=1)"] --> B["weight × e^(-0.3 × days_old)"]
    B --> C["Thread heat = SUM(article heats)"]
    C --> D["Parent totalHeat = SUM(child thread heats)"]
    D --> E{"totalHeat >= 8?"}
    E -->|Yes| F["●●● (Hot)"]
    E -->|No| G{"totalHeat >= 4?"}
    G -->|Yes| H["●● (Warm)"]
    G -->|No| I["● (Mild)"]

    style F fill:#ef4444,color:#fff,stroke:none
    style H fill:#f59e0b,color:#1a1a1a,stroke:none
    style I fill:#d4d4d4,color:#525252,stroke:none
```

## 5. Stories Tab Layout — Concept A (Hub Cards)

```mermaid
graph TD
    subgraph "Stories Tab"
        direction TB

        subgraph P1["Parent Card: US-Iran Tensions ●●●"]
            direction LR
            S1["Military<br/>72 arts ●●●"]
            S2["Gas Prices<br/>50 arts ●●●"]
            S3["Diplomacy<br/>10 arts ●●"]
            S4["Banks<br/>2 arts ●"]
        end

        subgraph P2["Parent Card: Fed Policy ●●"]
            direction LR
            S5["Rate Decision<br/>37 arts ●●"]
            S6["Dollar<br/>32 arts ●●"]
            S7["Trump vs Fed<br/>13 arts ●●"]
        end

        subgraph P3["Parent Card: Tariffs ●●"]
            direction LR
            S8["Supreme Court<br/>24 arts"]
            S9["Trade Deficit<br/>15 arts"]
        end

        subgraph Standalone["Standalone Stories"]
            direction TB
            T1["Gold Price Surge — 21 arts ●●"]
            T2["Warner Bros Acquisition — 19 arts ●●"]
            T3["AI Software Selloff — 25 arts ●"]
        end
    end

    P1 --> P2
    P2 --> P3
    P3 --> Standalone

    style P1 fill:#fef2f2,stroke:#ef4444
    style P2 fill:#eff6ff,stroke:#3b82f6
    style P3 fill:#fffbeb,stroke:#f59e0b
    style Standalone fill:#f9fafb,stroke:#d4d4d4
```

## 6. Thread Detail Page Layout

```mermaid
graph TD
    subgraph "Thread Detail /news/thread/[id]"
        direction TB

        A["Hero: Parent Title + Stats"]
        B["Sub-thread Filter Chips<br/>[All] [Military] [Gas] [Diplomacy] [Banks]"]
        C["Combined Timeline<br/>with sub-thread color tags"]
        D["Related Storylines<br/>(future: causal links)"]

        A --> B
        B --> C
        C --> D
    end

    style A fill:#1a1a1a,color:#fff,stroke:none
    style B fill:#f5f5f5,stroke:#e5e5e5
    style C fill:#fff,stroke:#e5e5e5
    style D fill:#f0fdf4,stroke:#86efac
```

## 7. Implementation Phases

```mermaid
gantt
    title Stories Tab Enhancement Roadmap
    dateFormat YYYY-MM-DD

    section Backend
    wsj_parent_threads table          :b1, 2026-03-06, 1d
    LLM parent grouping script        :b2, after b1, 2d
    Service layer update              :b3, after b2, 1d

    section Frontend Phase 1
    Hub Cards (Concept A)             :f1, after b3, 2d
    Standalone section                :f2, after f1, 1d

    section Frontend Phase 2
    Thread Detail Page (Concept C)    :f3, after f2, 3d
    Timeline with sub-thread tags     :f4, after f3, 2d

    section Polish
    Mobile responsive                 :p1, after f4, 1d
    Heat visualization tuning         :p2, after f4, 1d
```
