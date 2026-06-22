#!/bin/bash
set -e

echo "Starting deployment..."

echo "Pulling latest code..."
git pull origin main

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing production dependencies..."
pip install -r requirements/production.txt

echo "Applying migrations..."
python manage.py migrate --settings=config.settings.production

echo "Collecting static files..."
python manage.py collectstatic --noinput --settings=config.settings.production

echo "Restarting services..."
sudo systemctl restart gunicorn
sudo systemctl restart nginx

echo "Deployment completed."
