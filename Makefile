.PHONY: up down ingest inject clear investigate evals load tunnel test

up:            ## start the whole stack
	docker compose up -d --build

down:
	docker compose down

tunnel:        ## expose the agent publicly so Jira/GitHub webhooks can reach it (needs ngrok installed)
	ngrok http 8085

load:          ## generate background traffic
	python scripts/load_generator.py

ingest:        ## embed runbooks into pgvector for one user -- e.g. make ingest USER_ID=1 (runbooks are per-user; new users get this seeded automatically on registration)
	docker compose exec agent python -m rag.ingest $(USER_ID)

inject:        ## e.g. make inject FAULT=slow_db
	curl -s -X POST localhost:8001/faults/$(FAULT) | python -m json.tool

clear:         ## clear all injected faults
	curl -s -X DELETE localhost:8001/faults | python -m json.tool

investigate:   ## run the agent on the current situation (Week 3)
	curl -s -X POST localhost:8085/investigate -H 'Content-Type: application/json' -d '{"alert":"manual trigger"}' | python -m json.tool

evals:         ## run the eval harness against the demo-app faults
	docker compose exec agent python -m evals.run

test:          ## run the unit tests (tool modules + webhook auth) -- not installed in the prod image
	docker compose exec agent sh -c "pip install -q -r requirements-dev.txt && python -m pytest tests/ -v"
