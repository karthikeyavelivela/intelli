
**Authentication** (`auth` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| POST | `/api/auth/change-password` | change password | - | any signed-in user |
| POST | `/api/auth/forgot-password` | forgot password | - | public (no login) |
| POST | `/api/auth/login` | login | - | public (no login) |
| POST | `/api/auth/logout` | logout | - | public (no login) |
| GET | `/api/auth/me` | me | - | any signed-in user |
| PATCH | `/api/auth/me` | update me | - | any signed-in user |
| POST | `/api/auth/refresh` | refresh | - | public (no login) |
| POST | `/api/auth/register` | register | - | public (no login) |
| POST | `/api/auth/reset-password` | reset password | - | public (no login) |

**Workspaces, settings, audit log** (`workspaces` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/admin/api-usage` | api usage | `workspace.manage` | Admin |
| GET | `/api/admin/audit-logs` | audit logs | `audit.view` | Admin |
| GET | `/api/permissions/matrix` | permissions matrix | - | any signed-in user |
| GET | `/api/workspaces/current` | get workspace | - | any signed-in user |
| PATCH | `/api/workspaces/current` | rename workspace | `workspace.manage` | Admin |
| GET | `/api/workspaces/current/settings` | get settings | - | any signed-in user |
| PUT | `/api/workspaces/current/settings` | put settings | `workspace.manage` | Admin |

**Users and roles** (`users` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/users` | list users | - | any signed-in user |
| POST | `/api/users` | invite user | `user.manage` | Admin |
| DELETE | `/api/users/{user_id}` | remove user | `user.manage` | Admin |
| PATCH | `/api/users/{user_id}` | patch user | `user.manage` | Admin |

**Datasets, uploads and connections** (`datasets` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/connections` | list connections | - | any signed-in user |
| POST | `/api/connections` | create connection | `dataset.write` | Admin, Analyst |
| DELETE | `/api/connections/{cid}` | delete conn | `dataset.delete` | Admin |
| POST | `/api/connections/{cid}/import` | conn import | `dataset.write` | Admin, Analyst |
| GET | `/api/connections/{cid}/tables` | conn tables | `dataset.write` | Admin, Analyst |
| POST | `/api/connections/{cid}/test` | test conn | `dataset.write` | Admin, Analyst |
| GET | `/api/datasets` | list datasets | - | any signed-in user |
| POST | `/api/datasets/upload` | upload dataset | `dataset.write` | Admin, Analyst |
| DELETE | `/api/datasets/{dataset_id}` | delete dataset | `dataset.delete` | Admin |
| GET | `/api/datasets/{dataset_id}` | get dataset | - | any signed-in user |
| GET | `/api/datasets/{dataset_id}/jobs` | dataset jobs | - | any signed-in user |
| GET | `/api/datasets/{dataset_id}/preview` | preview | - | any signed-in user |
| POST | `/api/datasets/{dataset_id}/reprocess` | reprocess | `dataset.write` | Admin, Analyst |
| GET | `/api/datasets/{dataset_id}/status` | dataset status | - | any signed-in user |

**Metrics, workflow and versions** (`metrics` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/metrics` | list metrics | - | any signed-in user |
| POST | `/api/metrics` | create | `metric.write` | Admin, Analyst |
| GET | `/api/metrics/facets` | facets | - | any signed-in user |
| GET | `/api/metrics/graph` | graph | - | any signed-in user |
| DELETE | `/api/metrics/{mid}` | delete | `metric.write` | Admin, Analyst |
| GET | `/api/metrics/{mid}` | detail | - | any signed-in user |
| PATCH | `/api/metrics/{mid}` | update | `metric.write` | Admin, Analyst |
| POST | `/api/metrics/{mid}/approve` | metric approve | `metric.review` | Admin, Reviewer |
| GET | `/api/metrics/{mid}/audit` | metric audit | - | any signed-in user |
| POST | `/api/metrics/{mid}/deprecate` | metric deprecate | `metric.review` | Admin, Reviewer |
| GET | `/api/metrics/{mid}/diff` | diff | - | any signed-in user |
| POST | `/api/metrics/{mid}/publish` | metric publish | `metric.review` | Admin, Reviewer |
| POST | `/api/metrics/{mid}/reject` | metric reject | `metric.review` | Admin, Reviewer |
| POST | `/api/metrics/{mid}/rollback` | rollback | `metric.rollback` | Admin, Reviewer |
| POST | `/api/metrics/{mid}/submit` | metric submit | `metric.write` | Admin, Analyst |
| GET | `/api/metrics/{mid}/versions` | versions | - | any signed-in user |
| GET | `/api/versions/recent` | recent versions | - | any signed-in user |

**TARA metric generator** (`ai` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| POST | `/api/ai/generate-metric` | generate | `ai.generate` | Admin, Analyst |
| GET | `/api/ai/generations` | generations | `ai.generate` | Admin, Analyst |
| POST | `/api/ai/generations/{gid}/discard` | discard | `ai.generate` | Admin, Analyst |
| POST | `/api/ai/generations/{gid}/save` | save | `metric.write` | Admin, Analyst |
| GET | `/api/ai/status` | status | - | any signed-in user |

**Conflict detection** (`conflicts` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/conflicts` | list conflicts | `conflict.view` | Admin, Analyst, Business, Reviewer |
| POST | `/api/conflicts/detect` | detect | `conflict.detect` | Admin, Analyst, Reviewer |
| GET | `/api/conflicts/{cid}` | detail | `conflict.view` | Admin, Analyst, Business, Reviewer |
| POST | `/api/conflicts/{cid}/approve` | approve | `conflict.manage` | Admin, Reviewer |
| POST | `/api/conflicts/{cid}/assign` | assign | `conflict.manage` | Admin, Reviewer |
| POST | `/api/conflicts/{cid}/dismiss` | dismiss | `conflict.manage` | Admin, Reviewer |
| GET | `/api/conflicts/{cid}/events` | events | `conflict.view` | Admin, Analyst, Business, Reviewer |
| POST | `/api/conflicts/{cid}/reopen` | reopen | `conflict.manage` | Admin, Reviewer |
| POST | `/api/conflicts/{cid}/resolve` | resolve | `conflict.manage` | Admin, Reviewer |
| POST | `/api/conflicts/{cid}/review` | start review | `conflict.manage` | Admin, Reviewer |

**Formula validation** (`validation` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| POST | `/api/validation/formula` | validate formula | `formula.run` | Admin, Analyst, Reviewer |

**Formula execution** (`execution` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/execution/history` | history | `formula.run` | Admin, Analyst, Reviewer |
| POST | `/api/execution/run` | run | `formula.run` | Admin, Analyst, Reviewer |

**Ask TARA** (`chat` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| POST | `/api/chat/ask` | ask | `chat.ask` | Admin, Analyst, Business, Reviewer |
| POST | `/api/chat/ask/stream` | ask stream | `chat.ask` | Admin, Analyst, Business, Reviewer |
| GET | `/api/chat/conversations` | conversations | `chat.ask` | Admin, Analyst, Business, Reviewer |
| DELETE | `/api/chat/conversations/{cid}` | delete conversation | `chat.ask` | Admin, Analyst, Business, Reviewer |
| GET | `/api/chat/conversations/{cid}` | conversation | `chat.ask` | Admin, Analyst, Business, Reviewer |
| GET | `/api/chat/suggestions` | get suggestions | `chat.ask` | Admin, Analyst, Business, Reviewer |

**Dashboards** (`dashboards` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/dashboards` | list dashboards | - | any signed-in user |
| POST | `/api/dashboards` | create | `dashboard.write` | Admin, Analyst, Business |
| POST | `/api/dashboards/from-template` | from template | `dashboard.write` | Admin, Analyst, Business |
| GET | `/api/dashboards/templates` | templates | - | any signed-in user |
| POST | `/api/dashboards/widget-data` | preview widget | - | any signed-in user |
| DELETE | `/api/dashboards/{did}` | delete | `dashboard.write` | Admin, Analyst, Business |
| GET | `/api/dashboards/{did}` | get | - | any signed-in user |
| PATCH | `/api/dashboards/{did}` | update | `dashboard.write` | Admin, Analyst, Business |
| POST | `/api/dashboards/{did}/data` | data | - | any signed-in user |

**Evaluation** (`evaluation` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/evaluation/cases` | cases | `evaluation.view` | Admin, Analyst, Reviewer |
| GET | `/api/evaluation/latest` | latest | `evaluation.view` | Admin, Analyst, Reviewer |
| POST | `/api/evaluation/run` | run | `evaluation.run` | Admin, Analyst |
| GET | `/api/evaluation/runs` | runs | `evaluation.view` | Admin, Analyst, Reviewer |
| GET | `/api/evaluation/runs/{rid}` | get run | `evaluation.view` | Admin, Analyst, Reviewer |

**Reports and exports** (`reports` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/reports/{kind}` | export | `report.export` | Admin, Analyst, Business, Reviewer |

**Notifications and activity** (`notifications` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/activity` | activity | - | any signed-in user |
| GET | `/api/notifications` | list notifications | - | any signed-in user |
| POST | `/api/notifications/read-all` | mark all | - | any signed-in user |
| POST | `/api/notifications/{nid}/read` | mark read | - | any signed-in user |

**Main dashboard** (`overview` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/api/overview` | overview | - | any signed-in user |

**Health** (`health` router)

| Method | Path | Purpose | Capability | Roles allowed |
|---|---|---|---|---|
| GET | `/health` | health | - | public (no login) |
