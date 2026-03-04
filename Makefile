.PHONY: up down logs setup ceo venture test clean

# Start OpenFounder (database + dashboard)
up:
	docker compose up -d
	@echo ""
	@echo "OpenFounder is running!"
	@echo "  Dashboard: http://localhost:$${DASHBOARD_PORT:-8111}"
	@echo ""
	@echo "Next: create a venture with 'make venture name=\"My Startup\"'"

# Stop everything
down:
	docker compose down

# View logs
logs:
	docker compose logs -f

# Run database setup/migrations manually
setup:
	docker compose exec dashboard python3 -m openfounder setup

# Run the CEO loop once (requires ANTHROPIC_API_KEY in .env)
ceo:
	docker compose run --rm ceo

# Create a new venture
venture:
	@test -n "$(name)" || (echo "Usage: make venture name=\"My Startup\"" && exit 1)
	docker compose exec dashboard python3 -m openfounder venture create "$(name)"

# Run tests
test:
	docker compose exec dashboard python3 -m pytest tests/ -v

# Reset everything (removes database volume)
clean:
	docker compose down -v
	@echo "All data removed. Run 'make up' to start fresh."
