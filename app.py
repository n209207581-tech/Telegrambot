from flask import Flask, request, jsonify
import requests
import hmac
import hashlib
import base64
import time
import os
import json

app = Flask(__name__)

# === КЛЮЧИ ===
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
KUCOIN_API_KEY = os.getenv('KUCOIN_API_KEY')
KUCOIN_SECRET_KEY = os.getenv('KUCOIN_SECRET_KEY')
KUCOIN_PASSPHRASE = os.getenv('KUCOIN_PASSPHRASE')

print("=== KUCOIN TRADING BOT ===")

def encrypt_passphrase(secret_key, passphrase):
    """Шифрование passphrase для KuCoin"""
    return base64.b64encode(
        hmac.new(
            secret_key.encode('utf-8'),
            passphrase.encode('utf-8'),
            hashlib.sha256
        ).digest()
    ).decode('utf-8')

def send_telegram_message(message):
    """Отправка сообщения в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Telegram error: {e}")
        return False

def get_kucoin_balance():
    """Получение баланса с KuCoin"""
    try:
        path = "/api/v1/accounts"
        timestamp = str(int(time.time() * 1000))
        
        # Генерация подписи
        signature = base64.b64encode(
            hmac.new(
                KUCOIN_SECRET_KEY.encode('utf-8'),
                (timestamp + 'GET' + path).encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        # Шифруем passphrase
        encrypted_passphrase = encrypt_passphrase(KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE)
        
        headers = {
            'KC-API-KEY': KUCOIN_API_KEY,
            'KC-API-SIGN': signature,
            'KC-API-TIMESTAMP': timestamp,
            'KC-API-PASSPHRASE': encrypted_passphrase,
            'KC-API-KEY-VERSION': '2',
            'Content-Type': 'application/json'
        }
        
        url = f"https://api.kucoin.com{path}"
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"KuCoin Balance Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "data": data}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}", "details": response.text}
            
    except Exception as e:
        print(f"KuCoin error: {e}")
        return {"success": False, "error": str(e)}

def place_kucoin_order(symbol, side, quantity, order_type="market", price=None):
    """Размещение ордера на KuCoin"""
    try:
        path = "/api/v1/orders"
        timestamp = str(int(time.time() * 1000))
        
        body = {
            'clientOid': str(int(time.time())),
            'side': side.lower(),
            'symbol': symbol,
            'type': order_type,
            'size': str(quantity)
        }
        
        if price and order_type == "limit":
            body['price'] = str(price)
        
        # Генерация подписи
        body_str = json.dumps(body)
        signature = base64.b64encode(
            hmac.new(
                KUCOIN_SECRET_KEY.encode('utf-8'),
                (timestamp + 'POST' + path + body_str).encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        encrypted_passphrase = encrypt_passphrase(KUCOIN_SECRET_KEY, KUCOIN_PASSPHRASE)
        
        headers = {
            'KC-API-KEY': KUCOIN_API_KEY,
            'KC-API-SIGN': signature,
            'KC-API-TIMESTAMP': timestamp,
            'KC-API-PASSPHRASE': encrypted_passphrase,
            'KC-API-KEY-VERSION': '2',
            'Content-Type': 'application/json'
        }
        
        url = f"https://api.kucoin.com{path}"
        response = requests.post(url, headers=headers, json=body, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {"success": True, "data": data}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}", "details": response.text}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==================== МАРШРУТЫ ====================

@app.route('/')
def home():
    return '''
    ✅ <b>KuCoin Trading Bot на Render!</b>
    
    <b>Доступные команды:</b>
    /test - Тест Telegram
    /balance - Баланс KuCoin
    /buy/BTC-USDT/0.001 - Тест покупки
    /debug - Диагностика
    
    <b>Архитектура:</b>
    TradingView → Telegram → KuCoin (авто)
    '''

@app.route('/test')
def test():
    """Тест Telegram"""
    success = send_telegram_message(
        "🚀 <b>Бот запущен на Render.com!</b>\n\n"
        "📊 <b>Статус:</b> ✅ Работает\n"
        "🌍 <b>Хостинг:</b> Render (глобальный)\n"
        "💰 <b>Биржа:</b> KuCoin\n"
        "🔗 <b>API:</b> Готов к работе\n\n"
        "🎯 Тестируем авто-торговлю!"
    )
    if success:
        return "✅ Сообщение отправлено в Telegram!"
    else:
        return "❌ Ошибка отправки в Telegram"

@app.route('/balance')
def check_balance():
    """Проверка баланса KuCoin"""
    balance_result = get_kucoin_balance()
    
    if balance_result["success"]:
        message = "💰 <b>Баланс KuCoin:</b>\n\n"
        message += "✅ API подключен успешно!\n"
        
        try:
            accounts = balance_result["data"]["data"]
            # Ищем USDT баланс
            usdt_account = next((acc for acc in accounts if acc["currency"] == "USDT" and acc["type"] == "trade"), None)
            if usdt_account:
                message += f"💵 USDT: {float(usdt_account['balance']):.2f}"
            else:
                message += "🔍 USDT trade баланс не найден"
                
        except Exception as e:
            message += f"🔍 Ошибка парсинга: {str(e)}"
            
    else:
        message = f"❌ <b>Ошибка баланса:</b>\n{balance_result['error']}"
        if balance_result.get('details'):
            message += f"\n📋 {balance_result['details'][:100]}..."
    
    send_telegram_message(message)
    return "✅ Запрос баланса отправлен в Telegram"

@app.route('/buy/<symbol>/<quantity>')
def buy_crypto(symbol, quantity):
    """Покупка крипты через KuCoin"""
    result = place_kucoin_order(symbol, "buy", quantity)
    
    if result["success"]:
        message = f"✅ <b>Ордер создан!</b>\n\nСимвол: {symbol}\nКоличество: {quantity}\nТип: market"
    else:
        message = f"❌ <b>Ошибка ордера:</b>\n{result['error']}"
        if result.get('details'):
            message += f"\n📋 {result['details'][:100]}..."
    
    send_telegram_message(message)
    return "✅ Запрос на покупку обработан"

@app.route('/debug')
def debug():
    """Диагностика"""
    balance_result = get_kucoin_balance()
    
    debug_info = {
        'keys_loaded': {
            'telegram': bool(TELEGRAM_BOT_TOKEN),
            'kucoin_api': bool(KUCOIN_API_KEY),
            'kucoin_secret': bool(KUCOIN_SECRET_KEY),
            'kucoin_passphrase': bool(KUCOIN_PASSPHRASE)
        },
        'kucoin_balance': balance_result
    }
    
    return f"<pre>{json.dumps(debug_info, indent=2, ensure_ascii=False)}</pre>"

@app.route('/webhook/tradingview', methods=['POST', 'GET'])
def webhook():
    if request.method == 'GET':
        return "✅ Вебхук готов к приему данных от TradingView!"
    
    try:
        data = request.get_json()
        symbol = data.get('symbol', 'Unknown')
        price = data.get('price', 0)
        rsi = data.get('rsi', 50)
        
        message = f"""
📊 <b>СИГНАЛ ОТ TRADINGVIEW</b>

🎯 <b>Инструмент:</b> {symbol}
💰 <b>Цена:</b> ${price}
📈 <b>RSI:</b> {rsi}

⚡ <b>Рекомендация:</b> {'BUY' if float(rsi) < 35 else 'SELL' if float(rsi) > 65 else 'HOLD'}
"""
        send_telegram_message(message)
        return jsonify({"status": "success", "message": "Сигнал обработан"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
