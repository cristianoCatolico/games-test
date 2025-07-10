# games-test
Welcome to **Game test**, a game for testing python skills.

## 🛠️ Features
- **Game** Actions for the game time it right
- **Anayltics** Individual player statistics
- **Leaderboard** Ranking of top ten players on realtime, using websockets

## 🚀 Quick Start

### Prerequisites

#### Local
1. **Install Python 3.13.2.**
2. **Install pip**
3. **Create a virtual env before running.**
4. **Environment Variables**:
   - Configure the required environment variables in a `.env` file.
   - An example can be found in `.env.example` in the root directory
#### Container
1. **Install Docker & Docker Compose**.
2. **Environment Variables**:
   - Configure the required environment variables in a `.env` file.
   - An example can be found in `.env.example` in the root directory
  

### Steps locally
1. Clone this repository:
```bash
   git clone https://github.com/cristianoCatolico/games-test.git
   cd games-test
   ```
2. Build and run the service:
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload  
```
3. Documentation with swagger in url  `http://localhost:8000/docs`


### Steps with container
1. Clone this repository:
```bash
   git clone https://github.com/cristianoCatolico/games-test.git
   cd games-test
   ```
2. Build and run the service:
```bash
docker-compose up --build
```

### Testing
1. Run first the project and must be a database url, in our case we did it with sqlite
```bash
uvicorn app.main:app --reload  
```
2. In other terminal put the following command, since we have integration tests
```bash
pytest app/tests/ --asyncio-mode=auto --cov=app --cov-report=term-missing
```s