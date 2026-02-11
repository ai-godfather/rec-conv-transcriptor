.PHONY: install dev build start clean

# Install all dependencies (Python + Node)
install:
	pip install -e .
	cd frontend && npm install

# Start development servers (FastAPI with reload + Vite dev server)
dev:
	@echo "Starting backend on :8000 and frontend on :5173..."
	@echo "Open http://localhost:5173 for development"
	python3 -m transcriptor serve --reload &
	cd frontend && npm run dev

# Build frontend for production
build:
	cd frontend && npm run build

# Start production server (FastAPI serving built frontend)
start:
	@echo "Starting Transcriptor dashboard on http://localhost:8000"
	python3 -m transcriptor serve

# Remove build artifacts
clean:
	rm -rf frontend/dist frontend/node_modules/.tmp
