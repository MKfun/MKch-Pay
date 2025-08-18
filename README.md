# MKch Pay
Бот в Telegram для оплаты пасскода за звезды.  
В будущем реализуется выдача индивидуального пасскода для каждого после оплаты  
Создан и реализуется [saivan](https://t.me/saivann)  
Вся логика бота находится в main.py, а файл config.py используется для хранения токенов и заготовленных сообщении.  
Все построено на бибилиотеке [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)  
## Обновление 18.08.25
Обновил requirements.txt, добавил setup.bat для настройки на Windows, добавил start.bat для старта работы бота на Windows, сделал админку через команду /admin с функциями:
* Изменения минимальной цены ( **/setprice** )
* Автовыдача товара из PASSCODE_codes.txt ( **/autodelivery** )
* Добавление / Удаление админов ( **/addadmin** ,  **/removeadmin** )
* Список админов ( **/listadmins** )
* Статистика продаж ( **/stats** )
## Обновление 16.08.25
Добавил requirements.txt, сделал лого в приветственном сообщении.
