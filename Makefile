.PHONY: up down test logs clean build restart

up:
	docker-compose up -d --build
	@echo "Waiting for services to be healthy..."
	@sleep 10
	@echo "Services started! API available at http://localhost:8000"
	@echo "API docs available at http://localhost:8000/docs"

down:
	docker-compose down

test:
	docker-compose exec api pytest tests/ -v

logs:
	docker-compose logs -f api

clean:
	docker-compose down -v
	docker system prune -f

build:
	docker-compose build

restart:
	docker-compose restart api

health:
	@curl -s http://localhost:8000/health | python -m json.tool

stats:
	@curl -s http://localhost:8000/stats | python -m json.tool

data:
	@curl -s "http://localhost:8000/data?limit=10" | python -m json.tool
