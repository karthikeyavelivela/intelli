from conftest import find_metric, sales_dataset


def test_health(anon):
    r = anon.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "up"


def test_all_demo_logins(clients):
    for k, c in clients.items():
        me = c.get("/api/auth/me").json()["user"]
        assert me["email"].endswith(".demo")


def test_overview_and_lists(admin):
    ov = admin.get("/api/overview")
    assert ov.status_code == 200, ov.text
    j = ov.json()
    assert j["kpis"]["published_metrics"] >= 8
    assert j["charts"]["revenue_by_month"] and len(j["charts"]["revenue_by_month"]["data"]) > 3
    for url in ("/api/datasets", "/api/metrics", "/api/dashboards", "/api/conflicts", "/api/notifications", "/api/activity", "/api/chat/suggestions"):
        r = admin.get(url)
        assert r.status_code == 200, (url, r.text)


def test_sales_scale(admin):
    d = sales_dataset(admin)
    assert d["row_count"] >= 50000 and d["status"] == "ready"
