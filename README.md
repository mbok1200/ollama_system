# ollama_system
# перевірити наявність нашого конфига
ls -l /etc/nginx/sites-available/ollama_system.conf

# відключити дефолтну сторінку і включити наш сайт
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/ollama_system.conf /etc/nginx/sites-enabled/ollama_system.conf

# перевірити конфіг і перезапустити nginx
sudo nginx -t
sudo systemctl restart nginx

# перевірити що nginx проксить і що uvicorn запущений
curl -svS http://127.0.0.1:8000/health
curl -svS http://192.168.1.113/health
sudo journalctl -u nginx -n 200 --no-pager
sudo journalctl -u ollama_system -n 200 --no-pager