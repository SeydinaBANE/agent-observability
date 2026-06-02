#!/usr/bin/env python3
"""CLI de développement pour Agent Observability.

Utilisation :
  ./dev-cli.py start       # Démarre tout (postgres + redis + API + dashboard)
  ./dev-cli.py stop        # Arrête tout
  ./dev-cli.py test        # Lance les tests
  ./dev-cli.py ci          # CI complète (lint + test)
  ./dev-cli.py seed        # Seed des données de démo
  ./dev-cli.py health      # Vérifie l'état des services
  ./dev-cli.py logs        # Logs des services
  ./dev-cli.py reset       # Reset la base de données
"""

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent

api_process: subprocess.Popen | None = None
dashboard_process: subprocess.Popen | None = None


def _run(*args: str, capture: bool = False, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, capture_output=capture, text=True, **kwargs)


def _check_docker() -> None:
    r = _run("docker", "info", capture=True)
    if r.returncode != 0:
        print("❌ Docker n'est pas en cours d'exécution. Lance Docker Desktop.")
        sys.exit(1)


def _services_up() -> None:
    _check_docker()
    r = _run(
        "docker",
        "compose",
        "-f",
        "docker-compose.dev.yml",
        "up",
        "-d",
        "postgres",
        "redis",
        "--wait",
    )
    if r.returncode != 0:
        print("❌ Échec du démarrage des services.")
        sys.exit(1)
    print("✅ postgres + redis démarrés")


def _services_down() -> None:
    _run("docker", "compose", "-f", "docker-compose.dev.yml", "down")


def _api_up() -> subprocess.Popen:
    return subprocess.Popen(
        ["uvicorn", "api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=ROOT,
    )


def _dashboard_up() -> subprocess.Popen:
    return subprocess.Popen(
        ["streamlit", "run", "dashboard/app.py", "--server.port=8501"],
        cwd=ROOT,
    )


def cmd_start(args) -> None:
    _services_up()

    global api_process, dashboard_process
    print("🚀 Démarrage de l'API...")
    api_process = _api_up()
    time.sleep(3)

    print("🚀 Démarrage du dashboard...")
    dashboard_process = _dashboard_up()
    time.sleep(2)

    print("✅  Tout est lancé :")
    print("   API       → http://localhost:8000")
    print("   Docs      → http://localhost:8000/docs")
    print("   Dashboard → http://localhost:8501")
    print("   Arrêter   → ./dev-cli.py stop")


def cmd_stop(args) -> None:
    global api_process, dashboard_process
    for proc, name in [(api_process, "API"), (dashboard_process, "Dashboard")]:
        if proc and proc.poll() is None:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            print(f"⏹️  {name} arrêté")
    _services_down()
    print("✅  Tout est arrêté")


def cmd_api(args) -> None:
    """Démarre postgres + redis + API (sans dashboard)."""
    _services_up()
    print("🚀 API sur http://localhost:8000 | Docs sur http://localhost:8000/docs")
    p = _api_up()
    try:
        p.wait()
    except KeyboardInterrupt:
        p.terminate()
    finally:
        _services_down()


def cmd_dashboard(args) -> None:
    """Démarre le dashboard uniquement (API doit déjà tourner)."""
    print("🚀 Dashboard sur http://localhost:8501")
    p = _dashboard_up()
    try:
        p.wait()
    except KeyboardInterrupt:
        p.terminate()


def cmd_test(args) -> None:
    _services_up()
    pytest_args = ["tests/", "-v"]
    no_header = []

    if args.coverage:
        pytest_args = [
            "tests/",
            "-v",
            "--cov=api",
            "--cov=core",
            "--cov=workers",
            "--cov-report=term-missing",
        ]
    if args.quick:
        pytest_args += ["-x", "--no-header"]
        no_header = ["--no-header"]
    if args.file:
        pytest_args = [args.file, "-v", *no_header]
    if args.keywords:
        pytest_args += ["-k", args.keywords]
    if args.failfast:
        pytest_args += ["-x"]

    r = _run("pytest", *pytest_args)
    _services_down()
    sys.exit(r.returncode)


def cmd_lint(args) -> None:
    checks = [
        ("ruff check", ["ruff", "check", "."]),
        ("ruff format", ["ruff", "format", "--check", "."]),
        ("mypy", ["mypy", "api/", "core/", "workers/"]),
    ]
    failures = 0
    for name, cmd in checks:
        print(f"\n─── {name} ───")
        r = _run(*cmd)
        if r.returncode == 0:
            print("✅  OK")
        else:
            print("❌  ÉCHEC")
            failures += 1
    sys.exit(failures)


def cmd_ci(args) -> None:
    cmd_lint(args)
    print("\n" + "=" * 50)
    cmd_test(args)


def cmd_seed(args) -> None:
    _services_up()

    import uuid

    import httpx

    base = "http://localhost:8000"
    api_key = "demo-key-local-dev"
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}

    print("🌱 Seed des données de démonstration...")

    r = httpx.post(
        f"{base}/api/v1/tenants",
        json={
            "name": "Demo Corp",
            "slug": "demo",
            "api_key": api_key,
        },
        headers={"Content-Type": "application/json"},
    )
    if r.status_code == 201:
        print("✅  Tenant créé")
    elif r.status_code == 409:
        pass
    else:
        print(f"⚠️  Tenant: {r.status_code} {r.text}")

    agents = [
        {"name": "customer-support", "version": "2.1.0", "langgraph_version": "0.2.60"},
        {"name": "code-reviewer", "version": "1.3.0", "langgraph_version": "0.2.58"},
        {"name": "data-analyzer", "version": "1.0.0", "langgraph_version": "0.2.55"},
    ]
    agent_ids = []
    for agent in agents:
        r = httpx.post(f"{base}/api/v1/agents", json=agent, headers=headers)
        if r.status_code == 201:
            aid = r.json()["id"]
            agent_ids.append(aid)
            print(f"✅  Agent {agent['name']} créé (id={aid[:8]}...)")
        elif r.status_code == 200:
            aid = r.json()["id"]
            agent_ids.append(aid)

    import random

    statuses = ["completed", "completed", "completed", "completed", "error"]
    for aid in agent_ids:
        for i in range(15):
            dur = random.randint(200, 5000)
            tokens = random.randint(100, 3000)
            cost = round(tokens * 0.000002, 6)
            status = random.choice(statuses)
            payload = {
                "agent_id": aid,
                "duration_ms": dur,
                "total_tokens": tokens,
                "cost_usd": cost,
                "status": status,
                "input_preview": f"Requête test #{i + 1}",
                "output_preview": f"Réponse test #{i + 1}",
                "session_id": f"session-{uuid.uuid4().hex[:8]}",
            }
            if status == "error":
                payload["error"] = "RateLimitError: exceeded token quota"
            r = httpx.post(f"{base}/api/v1/ingest", json=payload, headers=headers)
        print(f"✅  15 runs injectés pour {agents[agent_ids.index(aid)]['name']}")

    print("🌱  Données de démonstration prêtes !")
    print("   Dashboard → http://localhost:8501")
    print("   API Docs  → http://localhost:8000/docs")


def cmd_health(args) -> None:
    _check_docker()

    r = _run("docker", "compose", "-f", "docker-compose.dev.yml", "ps", "--format", "json", capture=True)
    if r.returncode != 0:
        print("❌  Services Docker non disponibles")
        sys.exit(1)

    services = {"postgres": "❌", "redis": "❌"}
    for line in r.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 3:
            name = parts[0]
            status = parts[2]
            if "postgres" in name.lower():
                services["postgres"] = "✅" if "Up" in status else "❌"
            if "redis" in name.lower():
                services["redis"] = "✅" if "Up" in status else "❌"

    for name, icon in services.items():
        print(f"  {icon} {name}")

    import httpx

    try:
        resp = httpx.get("http://localhost:8000/health", timeout=3)
        data = resp.json()
        print(f"  ✅ API (v{data['version']} · {data['status']})")
    except Exception:
        print("  ❌ API (non disponible)")

    try:
        resp = httpx.get("http://localhost:8501", timeout=3)
        print(f"  ✅ Dashboard ({resp.status_code})")
    except Exception:
        print("  ❌ Dashboard (non disponible)")


def cmd_logs(args) -> None:
    svc = args.service or ""
    _run("docker", "compose", "-f", "docker-compose.dev.yml", "logs", "-f", svc)


def cmd_reset(args) -> None:
    print("⚠️  Ceci va SUPPRIMER toutes les données !")
    if args.force:
        confirm = "oui"
    else:
        confirm = input("Taper 'oui' pour confirmer : ")
    if confirm != "oui":
        print("Annulé.")
        return

    _services_down()
    _run("docker", "compose", "-f", "docker-compose.dev.yml", "down", "-v")
    print("✅  Volume supprimé, base reset.")
    _services_up()
    print("✅  Services prêts (base vide).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="CLI de développement Agent Observability",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  ./dev-cli.py start
  ./dev-cli.py test --coverage
  ./dev-cli.py test -f tests/test_api.py -k "test_health"
  ./dev-cli.py seed
  ./dev-cli.py health
  ./dev-cli.py reset --force
        """,
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("start", help="Démarre tout (postgres + redis + API + dashboard)")
    sub.add_parser("stop", help="Arrête tout")

    sub.add_parser("api", help="Démarre postgres + redis + API uniquement")
    sub.add_parser("dashboard", help="Démarre le dashboard uniquement")

    p_test = sub.add_parser("test", help="Lance les tests")
    p_test.add_argument("--coverage", "-c", action="store_true", help="Avec rapport de couverture")
    p_test.add_argument("--quick", "-q", action="store_true", help="Mode rapide (--no-header)")
    p_test.add_argument("--file", "-f", type=str, help="Fichier de test spécifique")
    p_test.add_argument("--keywords", "-k", type=str, help="Filtre par mot-clé")
    p_test.add_argument("--failfast", "-x", action="store_true", help="Stop au premier échec")

    sub.add_parser("lint", help="Lance ruff + mypy")
    sub.add_parser("ci", help="Lint + tests (CI pipeline)")
    sub.add_parser("seed", help="Seed des données de démonstration")
    sub.add_parser("reset", help="Reset la base de données").add_argument(
        "--force", "-f", action="store_true", help="Skip confirmation"
    )
    sub.add_parser("health", help="Vérifie l'état des services")

    p_logs = sub.add_parser("logs", help="Logs des services Docker")
    p_logs.add_argument("service", nargs="?", default="", help="Service spécifique (api, dashboard, worker...)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "start": cmd_start,
        "stop": cmd_stop,
        "api": cmd_api,
        "dashboard": cmd_dashboard,
        "test": cmd_test,
        "lint": cmd_lint,
        "ci": cmd_ci,
        "seed": cmd_seed,
        "health": cmd_health,
        "logs": cmd_logs,
        "reset": cmd_reset,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
