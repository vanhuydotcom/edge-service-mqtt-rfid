# RFID Edge Service Backend

FastAPI-based edge service for RFID security gate solution.

## Quick Start

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py
```

The service starts on http://localhost:8088

## Dependencies

Install all required dependencies:

```bash
pip install fastapi uvicorn pydantic pydantic-settings aiosqlite paho-mqtt httpx
```

For development/testing:

```bash
pip install pytest pytest-asyncio
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v --override-ini="addopts="

# Run specific test file
python -m pytest tests/test_decision.py -v --override-ini="addopts="
```

## API Endpoints

- `GET /health` - Health check
- `POST /v1/tags/in-cart` - Register QR codes in cart
- `POST /v1/tags/paid` - Mark QR codes as paid
- `POST /v1/tags/remove` - Remove QR codes (void/refund)
- `GET /v1/tags/lookup?qr_code=X` - Lookup by QR code
- `GET /v1/tags/lookup?epc=X` - Lookup by EPC (decodes to QR)
- `GET /v1/stats` - Get system statistics

