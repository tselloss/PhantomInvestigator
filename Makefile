.PHONY: up down ingest inject clear investigate evals load

up:            ## start the whole stack
	docker compose up -d --build

down:
	docker compose down

load:          ## generate background traffic (Week 2)
	python scripts/load_generator.py

ingest:        ## embed runbooks into pgvector (Week 5)
	docker compose exec agent python -m rag.ingest

inject:        ## e.g. make inject FAULT=slow_db
	curl -s -X POST localhost:8001/faults/$(FAULT) | python -m json.tool

clear:         ## clear all injected faults
	curl -s -X DELETE localhost:8001/faults | python -m json.tool

investigate:   ## run the agent on the current situation (Week 3)
	curl -s -X POST localhost:8085/investigate -H 'Content-Type: application/json' -d '{"alert":"manual trigger"}' | python -m json.tool

evals:         ## run the eval harness (Week 6)
	docker compose exec agent python -m evals.run
