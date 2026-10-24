<!-- subtitle: A three-page concept note for a non-technical reader -->
{{titlepage}}

{{toc}}

# The idea in plain language

Ask three people in a company "what was our revenue last quarter?" and you may get three different numbers. The Sales team counts the value of goods sold. The Finance team subtracts goods that customers returned. The Marketing team quotes the amount on the customer's invoice, which includes GST. Nobody is lying; they are using the same word for different things.

**IntelliMetrics AI** is a web application that fixes this. It keeps *one official definition for every business number*, notices automatically when departments disagree, keeps a permanent history of every change, and lets anyone ask questions in plain English to **TARA**, an assistant that answers only from those official definitions and says "I can't answer that" instead of guessing.

# The problem

* The same metric is defined differently in different places (spreadsheets, dashboards, reports).
* Nobody finds out until two reports are put side by side in a meeting.
* Changes to a definition are not recorded, so nobody can say who changed what or why.
* Non-technical staff cannot query the data themselves, and generic AI chatbots can produce confident but wrong numbers.

# The solution

| Step | What the user does | What the system does |
|---|---|---|
| 1. Bring data | Uploads a file or connects PostgreSQL / MySQL | Processes it in the background and profiles every column |
| 2. Define | Writes a formula, or describes the metric in English to TARA | Checks the formula against the real columns; the AI only drafts, a person decides |
| 3. Govern | Submits for review; a reviewer approves and publishes | Only one definition can be live; every change is a new, unchangeable version |
| 4. Detect | Clicks "Run conflict detection" | Compares all definitions; flags differences, rates severity, recommends a fix |
| 5. Resolve | Assigns, reviews, approves and resolves | Records every step; applies the decision as a new version |
| 6. Ask and see | Asks TARA, or opens a dashboard | Shows real numbers with the definition and filters used |

# What makes it different (novelty)

1. **The AI never produces numbers.** TARA turns a question into a structured *plan*; the plan is checked against approved metrics and executed through a restricted, safe formula engine. If the data cannot answer, it says so.
2. **Conflicts are found by the system.** Formula, aggregation, filters, unit, time window and dataset are compared automatically, and the result is measured: on {{bench.evaluation.conflict_detection.cases}} labelled test cases the detector scored precision {{bench.evaluation.conflict_detection.automated.precision}} and recall {{bench.evaluation.conflict_detection.automated.recall}}, compared with precision {{bench.evaluation.conflict_detection.naive_manual.precision}} for a simple text comparison.
3. **Nothing is ever overwritten.** Versions are immutable (enforced by the database itself); "rollback" creates a new version.
4. **Built for India.** Amounts in rupees with lakh/crore grouping, the April-to-March financial year, GST, festival seasons and IST.
5. **Safe by construction.** Users cannot run raw SQL; the formula language is parsed and compiled to parameterised queries, with time and row limits.

# Users and roles

| Role | Typical person | Main things they do |
|---|---|---|
| **Admin** | Head of data governance | Everything, including users, settings and the audit log |
| **Data Analyst** | Senior analyst | Upload data, define metrics, use TARA's generator and the Formula Lab, run evaluations |
| **Reviewer** | Finance controller | Approve and publish metrics, assign and resolve conflicts, roll back |
| **Business User** | Regional sales manager | Ask TARA, build dashboards, export reports |

Each company is a separate *workspace*; a user in one can never see another's data.

# The demonstration story (about ten minutes)

The demo company is a fictional retailer, *Bharat Retail Pvt Ltd*, with {{bench.dataset.rows}} synthetic sales lines in rupees.

1. The **Reviewer** runs conflict detection and sees that *Revenue* is defined three ways (official, Finance net of refunds, Marketing including GST).
2. The conflict is **assigned, reviewed and approved**, then **resolved** by renaming Finance's version; the system records a new version and an audit trail.
3. An **Analyst** tests `[Revenue] - SUM(refund_amount)` in the **Formula Lab**; a malicious input is rejected without running.
4. A **Business User** asks TARA: *"What was net revenue by month in the last quarter of this financial year?"*, *"Which 5 states had the highest sales this year?"*, *"What is the UPI vs COD split by region?"* and *"Compare Diwali-season sales with the previous quarter."* Each answer shows a table or chart, the definition used and the date range in DD-MMM-YYYY.
5. The **Sales Overview dashboard** shows the same governed Revenue.

# Expected outcomes

* One trusted definition per metric, with a complete audit trail.
* Faster discovery of definition conflicts (automated, repeatable, measured).
* Self-service answers for business users without risking wrong or unsafe queries.
* A reproducible, documented, tested reference implementation for the university evaluation.

# Technology summary

React and TypeScript front end; FastAPI back end; PostgreSQL (SQLite for local use); DuckDB and Parquet for fast analytics; Celery with Redis for background jobs; optional OpenAI or Gemini through the server only; Docker Compose for deployment; pytest, Vitest and Playwright for testing ({{tests.total}} automated tests). The full technology table is in the Project Report.

# Scope note

IntelliMetrics AI is an **academic capstone project** with synthetic demonstration data. It is not offered as a commercial product.
