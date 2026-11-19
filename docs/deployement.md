MyGPT — UAT Deployment Guide
Server: Ubuntu 22.04 LTS
Application: MyGPT
Deployment: Docker Compose
Project: inet-mygpt-uat
1. Server directories
Source: /home/uat/mygpt/source
Models: /home/uat/mygpt/storage/models
Tender data: /home/uat/mygpt/storage/tender_data
Logs: /home/uat/mygpt/storage/logs
2. Connect to server
ssh uat@192.168.50.52
3. Navigate to application
cd /home/uat/mygpt/source
4. First-time deployment
docker compose config -q
docker compose build
docker compose up -d
docker compose ps
5. Deploy code updates
Upload changed source files through WinSCP, then:
cd /home/uat/mygpt/source
docker compose up -d --build
docker compose ps
Docker reuses cached build layers where possible.
6. Build without cache
Use only when necessary:
docker compose build --no-cache
docker compose up -d
7. Application management
Start:
docker compose start
Stop temporarily:
docker compose stop
Restart:
docker compose restart
Stop and remove containers/network:
docker compose down
Do not use docker compose down -v for routine maintenance.
8. Logs and monitoring
All logs:
docker compose logs -f --tail=100
Backend logs:
docker compose logs -f backend
Frontend logs:
docker compose logs -f frontend
Container status:
docker compose ps
Resource monitoring:
docker stats
9. Test application
Frontend:
curl -I http://127.0.0.1:3103
Backend:
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/').read().decode())"
API documentation:
curl -I http://127.0.0.1:3103/docs
10. Persistent data
Never delete these directories during source updates:
/home/uat/mygpt/storage/models
/home/uat/mygpt/storage/tender_data
/home/uat/mygpt/storage/logs
Keep .env private and never commit it to Git.
11. Isolation
All MyGPT commands must be executed from /home/uat/mygpt/source.
Do not use global Docker cleanup commands that could remove resources belonging to INET Portal or i-See.
MyGPT runs independently under its own Compose project: inet-mygpt-uat.