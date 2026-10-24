| Capability | Admin | Data Analyst | Business User | Reviewer |
|---|:-:|:-:|:-:|:-:|
| View metrics catalog, datasets, dashboards (`catalog.view`) | Yes | Yes | Yes | Yes |
| Upload datasets / manage connections (`dataset.write`) | Yes | Yes | - | - |
| Delete datasets and connections (`dataset.delete`) | Yes | - | - | - |
| Create and edit metrics (`metric.write`) | Yes | Yes | - | - |
| Approve / reject / publish / deprecate metrics (`metric.review`) | Yes | - | - | Yes |
| Roll back a metric (creates a new version) (`metric.rollback`) | Yes | - | - | Yes |
| Use TARA metric generator (`ai.generate`) | Yes | Yes | - | - |
| Ask TARA (natural-language BI) (`chat.ask`) | Yes | Yes | Yes | Yes |
| View conflicts (`conflict.view`) | Yes | Yes | Yes | Yes |
| Run conflict detection (`conflict.detect`) | Yes | Yes | - | Yes |
| Assign / review / resolve conflicts (`conflict.manage`) | Yes | - | - | Yes |
| Formula Lab: validate and execute (`formula.run`) | Yes | Yes | - | Yes |
| Create / edit dashboards (`dashboard.write`) | Yes | Yes | Yes | - |
| View performance evaluation (`evaluation.view`) | Yes | Yes | - | Yes |
| Run performance evaluation (`evaluation.run`) | Yes | Yes | - | - |
| Export reports (`report.export`) | Yes | Yes | Yes | Yes |
| Manage users and roles (`user.manage`) | Yes | - | - | - |
| Manage workspace and settings (`workspace.manage`) | Yes | - | - | - |
| View audit log (`audit.view`) | Yes | - | - | - |
