1. Необходимо запустить Redis:  C:/Redis/redis-server.exe
2. В термнале в виртуальном окружении запустить:
	celery -A correspondence worker --pool=solo -l info
3. В  другом терминале в виртуальном окружении запустить:
	celery -A correspondence beat -l info
4. В еще другом терминеле запустить:
	manage.py runserver