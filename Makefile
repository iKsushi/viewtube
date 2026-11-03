.PHONY: up down logs test smoke backup
up:
	bash scripts/deploy.sh --demo
down:
	docker compose down
logs:
	docker compose logs --tail=100 -f api worker
test:
	bash scripts/test.sh
smoke:
	docker compose exec -T api python -m app.smoke --url http://web --allow-write
backup:
	bash scripts/backup.sh
