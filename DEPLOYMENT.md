# Deployment Guide - SSH to Server

## Option 1: Git-Based Deployment (Recommended)

If your code is in a Git repository, this is the cleanest approach:

### On Your Local Machine:
```bash
# 1. Commit your changes
git add .
git commit -m "Update code with latest changes"
git push origin main  # or your branch name
```

### On Server (via SSH):
```bash
# 1. SSH into your server
ssh user@72.52.132.145

# 2. Navigate to your project directory
cd /path/to/your/project

# 3. Pull latest changes
git pull origin main

# 4. Install/update dependencies (if requirements.txt changed)
source venv/bin/activate  # if using virtual environment
pip install -r requirements.txt

# 5. Restart the application
# If using systemd:
sudo systemctl restart warmprospect

# If using PM2:
pm2 restart warmprospect

# If running directly:
# Kill old process and restart
pkill -f "uvicorn main:app"
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```

## Option 2: rsync (Direct File Transfer)

Sync files directly from local to server:

```bash
# From your local machine
rsync -avz --exclude '.env' \
          --exclude '__pycache__' \
          --exclude '*.pyc' \
          --exclude '.git' \
          --exclude 'venv' \
          --exclude 'data/*.faiss' \
          --exclude 'data/*.jsonl' \
          ./ user@72.52.132.145:/path/to/your/project/

# Then SSH and restart
ssh user@72.52.132.145 "cd /path/to/your/project && \
  source venv/bin/activate && \
  pip install -r requirements.txt && \
  sudo systemctl restart warmprospect"
```

## Option 3: Deployment Script

Create a simple deployment script:

### Create `deploy.sh` on your local machine:

```bash
#!/bin/bash

# Configuration
SERVER_USER="your_username"
SERVER_HOST="72.52.132.145"
SERVER_PATH="/path/to/your/project"
LOCAL_PATH="."

echo "🚀 Deploying to server..."

# Sync files (excluding sensitive/unnecessary files)
rsync -avz --delete \
  --exclude '.env' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'venv' \
  --exclude '.venv' \
  --exclude 'data/*.faiss' \
  --exclude 'data/*.jsonl' \
  --exclude '.DS_Store' \
  "$LOCAL_PATH/" "$SERVER_USER@$SERVER_HOST:$SERVER_PATH/"

echo "📦 Files synced. Restarting application..."

# SSH and restart application
ssh "$SERVER_USER@$SERVER_HOST" << 'EOF'
cd /path/to/your/project
source venv/bin/activate 2>/dev/null || true
pip install -r requirements.txt --quiet
sudo systemctl restart warmprospect || pm2 restart warmprospect || {
  pkill -f "uvicorn main:app"
  nohup uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
}
echo "✅ Deployment complete!"
EOF
```

Make it executable:
```bash
chmod +x deploy.sh
./deploy.sh
```

## Option 4: Manual Step-by-Step

### Step 1: Transfer Files
```bash
# Create a tarball (excluding unnecessary files)
tar --exclude='.env' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='venv' \
    --exclude='data/*.faiss' \
    -czf deploy.tar.gz .

# Copy to server
scp deploy.tar.gz user@72.52.132.145:/tmp/

# SSH and extract
ssh user@72.52.132.145
cd /path/to/your/project
tar -xzf /tmp/deploy.tar.gz
rm /tmp/deploy.tar.gz
```

### Step 2: Update Dependencies
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Restart Application
```bash
# Option A: If using systemd service
sudo systemctl restart warmprospect
sudo systemctl status warmprospect

# Option B: If using PM2
pm2 restart warmprospect
pm2 logs warmprospect

# Option C: Manual restart
# Find the process
ps aux | grep "uvicorn main:app"

# Kill it
kill <PID>

# Restart
cd /path/to/your/project
source venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > app.log 2>&1 &
```

## Important Notes

### 1. **Never Overwrite `.env` File**
Your `.env` file on the server contains production secrets. Always exclude it:
```bash
--exclude '.env'
```

### 2. **Backup Before Deploying**
```bash
# On server, before deploying
cd /path/to/your/project
cp -r . ../backup-$(date +%Y%m%d-%H%M%S)
```

### 3. **Check Application Status**
```bash
# Check if app is running
curl http://localhost:8000/health

# Check logs
tail -f app.log
# or
journalctl -u warmprospect -f  # if using systemd
```

### 4. **Database Migrations** (if needed)
```bash
# If you have database changes
cd /path/to/your/project
source venv/bin/activate
python scripts/migrate_db.py
```

## Quick One-Liner (Git-based)

If you use Git and have SSH key set up:

```bash
# Local: Push to git
git push

# Server: One command to update
ssh user@72.52.132.145 "cd /path/to/project && git pull && source venv/bin/activate && pip install -r requirements.txt && sudo systemctl restart warmprospect"
```

## Troubleshooting

**Permission Denied:**
```bash
# Make sure you have write permissions
ssh user@server
sudo chown -R $USER:$USER /path/to/your/project
```

**Port Already in Use:**
```bash
# Find what's using port 8000
sudo lsof -i :8000
# Kill it
kill <PID>
```

**Application Not Starting:**
```bash
# Check logs
tail -f app.log
# Or run directly to see errors
cd /path/to/your/project
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```
