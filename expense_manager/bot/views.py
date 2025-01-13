import json
import uuid
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from telegram import InlineKeyboardButton
from room.models import Room, Expense, Payment
from user.models import TelegramUser
import environ
import requests
from .models import RoomCreationSession, ExpenseCreationSession, AddRoomMemberSession
import random
import string


env = environ.Env()
environ.Env.read_env("../expense_manager/.env")
API_KEY = env("API_KEY")
url = f"https://api.telegram.org/bot{API_KEY}/sendMessage"


def generate_unique_room_code():
    characters = string.ascii_letters + string.digits  # Contains a-z, A-Z, and 0-9
    while True:
        room_code = ''.join(random.choices(characters, k=16))  # Generate a 16-character random string
        if not Room.objects.filter(code=room_code).exists():  # Check uniqueness in the database
            return room_code
    

def send_message(message, CHAT_ID):
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message
    })

def send_message_with_keyboard(message, keyboard, CHAT_ID):
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message,
        "reply_markup": json.dumps({"keyboard": keyboard})
    })
room_creation_cancle_keyboard = {
    "inline_keyboard": [
        [
            {
                "text": "لغو",
                "callback_data": "cancel_room_creation"
            }
        ]
    ]
}

def start(CHAT_ID):
    
    user, created = TelegramUser.objects.get_or_create(chat_id=CHAT_ID)
    
    if user.username:
        message = f"سلام {user.username}! به ربات مدیریت هزینه‌ها خوش آمدید!"
    else:
        message = "سلام به ربات مدیتریت هزینه ها خوش آمدید لطفا یوزرنیم خود را به صورت @username وارد کنید"
    
    send_message(message, CHAT_ID)

def create_username(CHAT_ID, username):
    user, created = TelegramUser.objects.get_or_create(chat_id=CHAT_ID)
    if user.username:
        message = "شما قبلا یوزرنیم دارید"
    else:
        user.username = username
        user.save()
        message = "یوزرنیم شما با موفقیت ثبت شد"
    send_message(message, CHAT_ID)

def send_main_menu(CHAT_ID):
    keyboard = {
        "inline_keyboard": [
            [{"text": "ساخت اتاق جدید", "callback_data": "create_room"}],
            [{"text": "دیدن یوزرنیم خودم", "callback_data": "show_username"}],
            [{"text": "دیدن اتاق های من", "callback_data": "view_my_rooms"}],
        ]
    }
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": "سلام! انتخاب کنید چه کاری می‌خواهید انجام دهید:",
        "reply_markup": json.dumps(keyboard)
    })

def start_create_room(CHAT_ID):
    send_message("لطفا نام اتاق را به شکل نام = نام وارد کنید ", CHAT_ID)

def send_room_main_menu(CHAT_ID, room):
    keyboard = {
        "inline_keyboard": [
            [{"text": "دیدن اعضای اتاق", "callback_data": f"view_room_members={room.id}"}],
            [{"text": "دیدن بدهکاری های من", "callback_data": f"view_my_debts={room.id}"}],
            [{"text": "دیدن بستانکاری های من", "callback_data": f"view_my_credits={room.id}"}],
            [{"text": "افزودن هزینه جدید", "callback_data": f"add_expense={room.id}"}],
            [{"text": "اضافه کردن اعضا", "callback_data": f"add_room_members={room.id}"}],
            [{"text": "بازگشت به منوی اصلی", "callback_data": "main_menu"}],
        ]
    }
    response = requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": f"منوی اتاق {room.name}",
        "reply_markup": json.dumps(keyboard) 
    })

@csrf_exempt
def telegram_webhook(request):
    if request.method == 'POST':
        data = json.loads(request.body)
            
        if "message" in data and "text" in data["message"]:
            message = data["message"]["text"].strip()
            chat_id = data["message"]["chat"]["id"]
            
        elif "callback_query" in data:
            message = data["callback_query"]["data"]
            chat_id = data["callback_query"]["message"]["chat"]["id"]
        if message == "/start":
            start(chat_id)
            telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
            if telegram_user.username is not None:
                send_main_menu(chat_id)

        elif message.startswith("@"):
            username = message.split("@")[1]
            create_username(chat_id, username)
            telegram_user = TelegramUser.objects.filter(username=username).first()
            if telegram_user:
                send_main_menu(chat_id)
        
        elif message == "create_room":
            start_create_room(chat_id)
        
        elif message == "cancel_room_creation":
            session = RoomCreationSession.objects.filter(user__chat_id=chat_id)
            if session:
                session.delete()
                send_message("از ساخت اتاق کنسل شد.", chat_id)
            else:
                send_message("اتاقی وجود نداشت برای کنسل کردن", chat_id)
            
            send_main_menu(chat_id)

        
        elif message.startswith("نام ="):
            room_name = message.split("=")[1].strip()
            telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
            room_creation_session = RoomCreationSession.objects.filter(user=telegram_user).first()
            if room_creation_session:
                room_creation_session.delete()
            RoomCreationSession.objects.create(user=telegram_user, name=room_name)
            send_message("لطفا توضیحات اتاق را به صورت توضیحات = توضیحات وارد کنید", chat_id)


        elif message.startswith("توضیحات ="):
            room_description = message.split("=")[1].strip()
            session = RoomCreationSession.objects.filter(user__chat_id=chat_id).first()
            if session:
                session.description = room_description
                session.save()
                send_message("لطفا یوزرنیم هایی که در اتاق می‌خواهید قرار دهید را به صورت usernames = username1,username2,... وارد کنید", chat_id)
            else :
                send_message("لطفا ابتدا نام اتاق را وارد کنید", chat_id)
                send_main_menu(chat_id)
        elif message.startswith("usernames ="):
            usernames = message.split("=")[1].strip().split(",")
            session = RoomCreationSession.objects.filter(user__chat_id=chat_id).first()
            response = ''
            if session:
                room = Room.objects.create(name=session.name, description=session.description, admin=session.user, code = generate_unique_room_code())
                for username in usernames:
                    user = TelegramUser.objects.filter(username=username.strip()).first()
                    if user:
                        room.members.add(user)
                        response += f"کاربر {user.username} به اتاق اضافه شد\n"
                    else:
                        response += f"کاربر {username} یافت نشد\n"
                room.members.add(session.user)
                send_message(response, chat_id)
                session.delete()
                send_main_menu(chat_id)
            else:
                send_message("لطفا ابتدا نام اتاق و توضیحات را وارد کنید", chat_id)
        
        elif message == "show_username":
            telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
            if telegram_user:
                send_message(f"یوزرنیم شما: {telegram_user.username}", chat_id)
                send_main_menu(chat_id)
            else:
                send_message("شما یوزرنیمی ندارید. لطفا ابتدا یوزرنیم خود را ثبت کنید.", chat_id)
        
        elif message == "view_my_rooms":
            telegram_user = TelegramUser.objects.get(chat_id=chat_id)
            rooms = telegram_user.rooms.all()
            if rooms:
                response = "اتاق های شما:\n"
                for room in rooms:
                    response += f"{room.name}\n{room.description}\ncode = /{room.code}\n"
                send_message(response, chat_id)
                send_main_menu(chat_id)
            else:
                send_message("شما در هیچ اتاقی عضو نیستید.", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("/") and message != "/start":
            code = message[1:]
            room = Room.objects.filter(code=code).first()
            if room:
                telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
                if telegram_user:
                    if telegram_user in room.members.all():
                        send_room_main_menu(chat_id, room)
                    else:
                        send_message("شما در این اتاق عضو نیستید.", chat_id)
                        send_main_menu(chat_id)
                else:
                    send_message("شما یوزرنیمی ندارید. لطفا ابتدا یوزرنیم خود را ثبت کنید.", chat_id)
                    send_main_menu(chat_id)
            else:
                send_message("اتاق یافت نشد.", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("view_room_members"):
            room_id = int(message.split("=")[1].strip())
            room = Room.objects.filter(id=room_id).first()
            if room:
                members = room.members.all()
                response = "اعضای اتاق:\n"
                for member in members:
                    response += f"{member.username}\n"
                send_message(response, chat_id)
                send_room_main_menu(chat_id, room)
            else:
                send_message("اتاق یافت نشد.", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("add_expense"):
            room_id = int(message.split("=")[1].strip())
            room = Room.objects.filter(id=room_id).first()
            if room:
                telegram_user = TelegramUser.objects.filter(chat_id=chat_id).first()
                expense_creation_session_bef = ExpenseCreationSession.objects.filter(payer=telegram_user).first()
                if expense_creation_session_bef:
                    expense_creation_session_bef.delete()
                if telegram_user:
                    if telegram_user in room.members.all():
                        expense_creation_session = ExpenseCreationSession.objects.create(room=room, payer=telegram_user)
                        send_message("لطفا نام هزینه را به صورت نام هزینه = نام وارد کنید ", chat_id)
                    else:
                        send_message("شما در این اتاق عضو نیستید.", chat_id)
                        send_main_menu(chat_id)
                else:
                    send_message("شما یوزرنیمی ندارید. لطفا ابتدا یوزرنیم خود را ثبت کنید.", chat_id)
                    send_main_menu(chat_id)
            
        elif message.startswith("نام هزینه"):
            expense_creation_session = ExpenseCreationSession.objects.filter(payer__chat_id=chat_id).first()
            if expense_creation_session:
                expense_name = message.split("=")[1].strip()
                expense_creation_session.name = expense_name
                expense_creation_session.save()
                send_message("لطفا مبلغ هزینه را به صورت مبلغ هزینه = مبلغ وارد کنید", chat_id)
            else:
                send_message("لطفا ابتدا یک اتاق را انتخاب کنید", chat_id)
                send_main_menu(chat_id)

        elif message.startswith("مبلغ هزینه"):
            expense_creation_session = ExpenseCreationSession.objects.filter(payer__chat_id=chat_id).first()
            if expense_creation_session:
                expense_amount = int(message.split("=")[1].strip())
                expense_creation_session.amount = expense_amount
                expense_creation_session.save()
                send_message("لطفا توضیحات هزینه را به صورت توضیحات هزینه = توضیحات وارد کنید", chat_id)
            elif expense_creation_session and not expense_creation_session.name:
                send_message("لطفا از ابتدا شروع کن و برای هزینه اسم انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            else:
                send_message("لطفا ابتدا یک اتاق را انتخاب کنید", chat_id)
                send_main_menu(chat_id)
        elif message.startswith("توضیحات هزینه"):
            expense_creation_session = ExpenseCreationSession.objects.filter(payer__chat_id=chat_id).first()
            if expense_creation_session:
                expense_description = message.split("=")[1].strip()
                expense_creation_session.description = expense_description
                expense_creation_session.save()
                send_message(" حالا یوزرنیم افرادی که میخواهی ثبت کنی را به شکل eusernames = username1, username2, ... وارد کن", chat_id)
            elif expense_creation_session and not expense_creation_session.expense_name:
                send_message("لطفا از ابتدا شروع کن و برای هزینه اسم انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            elif expense_creation_session and not expense_creation_session.expense_amount:
                send_message("لطفا از ابتدا شروع کن و برای هزینه مبلغ انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            else:
                send_message("لطفا ابتدا یک اتاق را انتخاب کنید", chat_id)
                send_main_menu(chat_id)
        elif message.startswith("eusernames"):
            expense_creation_session = ExpenseCreationSession.objects.filter(payer__chat_id=chat_id).first()
            room = expense_creation_session.room
            flag = False
            if expense_creation_session:
                eusernames = message.split("=")[1].strip()
                eusernames_list = eusernames.split(",")
                response = "کاربرانی که انتخاب کردید:\n"
                for username in eusernames_list:
                    user = TelegramUser.objects.filter(username=username.strip()).first()
                    if user and user in room.members.all():
                        expense_creation_session.participants.add(user)
                        expense_creation_session.save()
                        response += f"{user.username}\n"
                        flag = True
                    elif user and user not in room.members.all():
                        response += f"{user.username} - این کاربر در این اتاق عضو نیست\n"
                    elif user and user in expense_creation_session.participants.all():
                        response += f"{user.username} - این کاربر قبلا انتخاب شده است\n"
                    else:
                        response += f"{username.strip()} - کاربری یافت نشد\n"
                if flag :
                    expense = Expense.objects.create(
                        room=room,
                        name=expense_creation_session.name,
                        amount=expense_creation_session.amount,
                        description=expense_creation_session.description,
                        payer = expense_creation_session.payer,
                    )
                    expense.participants.set(expense_creation_session.participants.all())  
                    payer = expense.payer
                    amount = expense.amount / (len(expense.participants.all()) + 1)
                    for participant in expense.participants.all():
                        if participant != payer:
                            payment = Payment.objects.create(
                                expense=expense,
                                payer=payer,
                                participant=participant,
                                amount=amount)
                    expense_creation_session.delete()
                    send_message(response, chat_id)
                    send_message("هزینه با موفقیت اضافه شد", chat_id)
                    send_room_main_menu(chat_id, room)
                
                else :
                    send_message("هیچ کاربری انتخاب نشده است", chat_id)
                    send_main_menu(chat_id)
                    expense_creation_session.delete()
            elif expense_creation_session and not expense_creation_session.expense_name:
                send_message("لطفا از ابتدا شروع کن و برای هزینه اسم انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            elif expense_creation_session and not expense_creation_session.expense_amount:
                send_message("لطفا از ابتدا شروع کن و برای هزینه مبلغ انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            elif expense_creation_session and not expense_creation_session.description:
                send_message("لطفا از ابتدا شروع کن و برای هزینه توضیحات انتخاب کن", chat_id)
                expense_creation_session.delete()
                send_main_menu(chat_id)
            else:
                send_message("لطفا ابتدا یک اتاق را انتخاب کنید", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("view_my_debts"):
            user = TelegramUser.objects.filter(chat_id=chat_id).first()
            room_id = message.split("=")[1].strip()
            room = Room.objects.filter(id=room_id).first()
            if room:
                if user:
                    debts = Payment.objects.filter(participant=user)
                    if debts.exists():
                        response = "لیست سود و زیان شما:\n"
                        for debt in debts:
                            response += f"شما باید به {debt.payer.username} {debt.amount} تومان بپردازید\n"
                        send_message(response, chat_id)
                        send_room_main_menu(chat_id, room)
                    else:
                        send_message("شما هیچ سود و زیانی ندارید", chat_id)
                        send_room_main_menu(chat_id, room)
                else:
                    send_message("کاربری یافت نشد", chat_id)
                    send_main_menu(chat_id)
            else:
                send_message("اتاق یافت نشد", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("view_my_credits"):
            user = TelegramUser.objects.filter(chat_id=chat_id).first()
            room_id = message.split("=")[1].strip()
            room = Room.objects.filter(id=room_id).first()
            if room:
                if user:
                    debts = Payment.objects.filter(payer=user)
                    if debts.exists():
                        response = "لیست سود شما:\n"
                        for debt in debts:
                            response += f"شما باید از {debt.participant.username} {debt.amount} تومان بگیرید\n"
                        send_message(response, chat_id)
                        send_room_main_menu(chat_id, room)
                    else:
                        send_message("شما هیچ سودی ندارید")
                        send_room_main_menu(chat_id, room)
                else:
                    send_message("کاربری یافت نشد", chat_id)
                    send_main_menu(chat_id)
            else:
                send_message("اتاق یافت نشد", chat_id)
                send_main_menu(chat_id)
        
        elif message.startswith("add_room_members"):
            room_id = message.split("=")[1].strip()
            room = Room.objects.filter(id=room_id).first()
            user = TelegramUser.objects.filter(chat_id=chat_id).first()
            if user:
                if room:
                    send_message("لطفا اسم کاربر را به شکل added_username = username انتخاب کنید", chat_id)
                    room_add_member_session = AddRoomMemberSession.objects.filter(user=user).first()
                    if room_add_member_session:
                        room_add_member_session.delete()
                    AddRoomMemberSession.objects.create(room=room, user=user)
                else:
                        send_message("اتاق یافت نشد", chat_id)
                        send_main_menu(chat_id)
            else:
                send_message("کاربری یافت نشد", chat_id)
                send_main_menu(chat_id)

        elif message.startswith("added_username ="):
            room_add_member_session = AddRoomMemberSession.objects.filter(user__chat_id=chat_id).first()
            username = message.split("=")[1].strip()
            if room_add_member_session:
                room = room_add_member_session.room
                if room:
                    user = TelegramUser.objects.filter(username=username).first()
                    if user:
                        if user in room.members.all():
                            send_message("کاربر در اتاق وجود دارد", chat_id)
                            room_add_member_session.delete()
                            send_room_main_menu(chat_id, room)
                        else:
                            room.members.add(user)
                            room.save()
                            send_message("کاربر با موفقیت به اتاق اضافه شد", chat_id)
                            room_add_member_session.delete()
                            send_room_main_menu(chat_id, room)
                    else:
                            send_message("کاربر یافت نشد", chat_id)
                            room_add_member_session.delete()
                            send_room_main_menu(chat_id, room)
                else:
                        send_message("اتاق یافت نشد", chat_id)
                        room_add_member_session.delete()
                        send_main_menu(chat_id)
            else:
                    send_message("اتاق و سشن یافت نشد لطقا ازاول امتحان کنید", chat_id)
                    send_main_menu(chat_id)
        elif message == "main_menu":
            send_main_menu(chat_id)

        else:
                send_message("دستور یافت نشد", chat_id)
                room_add_member_session = AddRoomMemberSession.objects.filter(user__chat_id=chat_id).first()
                if room_add_member_session:
                    room_add_member_session.delete()
                
                room_creation_session = RoomCreationSession.objects.filter(user__chat_id=chat_id).first()
                if room_creation_session:
                    room_creation_session.delete()

                expense_creation_session = ExpenseCreationSession.objects.filter(payer__chat_id=chat_id).first()
                if expense_creation_session:
                    expense_creation_session.delete()


                send_main_menu(chat_id)


        return HttpResponse('OK', status=200)
    else:
        return HttpResponse('Invalid request method', status=405)