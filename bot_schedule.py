import telebot
from telebot import types
import pymysql
import os
import pandas as pd
import datetime

# Иерархия данных
DATA_HIERARCHY = {
    "ИФМиКН": {
        "Бакалавриат (очное)": {
            1: ["3301", "3302", "3303", "3304", "3305", "3309"],
            2: ["3201", "3202", "3203", "3205", "3206"],
            3: ["3101", "3102", "3103", "3104", "3105", "3108"],
            4: ["3001", "3002", "3007", "3008"],
            5: ["3902", "3903", "3907", "3910"],
        },
        "Магистратура": {
            1: ["3331"],
            2: ["3231", "3238"],
        },
    },
}

# Настройки бота и БД
TOKEN = '1971114447:AAEuqjrt5no8_-COr-AHkG12slb3iL1qjHI'
bot = telebot.TeleBot(TOKEN)

# Подключение к базе данных
connection = pymysql.connect(host='localhost', user='root', password='20122001', database='bot')
cursor = connection.cursor()

def save_user_data(user_id, faculty, form_of_education, course, group_name, date):
    cursor.execute("""
        INSERT INTO users (user_id, faculty, form_of_education, course, group_name, last_shown_date)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE faculty=%s, form_of_education=%s, course=%s, group_name=%s, last_shown_date=%s
    """, (user_id, faculty, form_of_education, course, group_name, None, faculty, form_of_education, course, group_name, date))
    connection.commit()

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id

    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()

    if user:  # Если пользователь уже существует в базе данных
        faculty = user[1]
        group_name = user[4]  # предполагая, что group_name находится в 5-м столбце
        show_schedule_on_start(message, group_name, faculty)
    else:
        markup = types.InlineKeyboardMarkup()
        for faculty in DATA_HIERARCHY.keys():
            markup.add(types.InlineKeyboardButton(text=faculty, callback_data=f"faculty_{faculty}"))
        bot.send_message(message.chat.id, "Выберите факультет:", reply_markup=markup)

def show_schedule_on_start(message, group_name, faculty):
    schedule_path = os.path.join(os.getcwd(), f"{faculty}\{group_name}.xlsx")
    try:
        df = pd.read_excel(schedule_path)
        current_week_type = get_current_week_type(date_ranges)
        
        response = format_schedule(df, current_week_type)
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="Изменить данные", callback_data="change_data"))
        markup.add(types.InlineKeyboardButton(text="Обновить расписание", callback_data=f"show_schedule_{group_name}"))

        bot.send_message(message.chat.id, response, reply_markup=markup, parse_mode='Markdown')
    except Exception as e:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text="Изменить данные", callback_data="change_data"))
        bot.send_message(message.chat.id, f"Ошибка при загрузке расписания для группы {group_name}. Причина: {e}. Пожалуйста, попробуйте позже.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("faculty_"))
def faculty_selected(call):
    faculty = call.data.split("_")[1]
    markup = types.InlineKeyboardMarkup()
    for form_of_education in DATA_HIERARCHY[faculty].keys():
        markup.add(types.InlineKeyboardButton(text=form_of_education, callback_data=f"form_{faculty}_{form_of_education}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Вы выбрали факультет: {faculty}. Теперь выберите уровень образования:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("form_"))
def form_selected(call):
    faculty, form_of_education = call.data.split("_")[1], call.data.split("_")[2]
    markup = types.InlineKeyboardMarkup()
    for course in DATA_HIERARCHY[faculty][form_of_education].keys():
        markup.add(types.InlineKeyboardButton(text=str(course), callback_data=f"course_{faculty}_{form_of_education}_{course}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Вы выбрали уровень образования: {form_of_education}. Теперь выберите курс:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("course_"))
def course_selected(call):
    faculty, form_of_education, course = call.data.split("_")[1], call.data.split("_")[2], int(call.data.split("_")[3])
    markup = types.InlineKeyboardMarkup()
    for group in DATA_HIERARCHY[faculty][form_of_education][course]:
        markup.add(types.InlineKeyboardButton(text=group, callback_data=f"group_{faculty}_{form_of_education}_{course}_{group}"))
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Вы выбрали курс: {course}. Теперь выберите группу:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("group_"))
def group_selected(call):
    faculty, form_of_education, course, group = call.data.split("_")[1], call.data.split("_")[2], int(call.data.split("_")[3]), call.data.split("_")[4]
    
    save_user_data(call.from_user.id, faculty, form_of_education, course, group, None)
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="Показать расписание", callback_data=f"show_schedule_{group}_{faculty}"))
    
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Спасибо за предоставленную информацию! Вы выбрали:\n\nФакультет: {faculty}\nФорма обучения: {form_of_education}\nКурс: {course}\nГруппа: {group}", reply_markup=markup)


days = ["Понедельник",
        "Вторник",
        "Среда",
        "Четверг",
        "Пятница",
        "Суббота"]
        
type_of_class = ["Лекция",
                 "Семинар",
                 "Лабораторная работа",
                 "Час куратора",
                 "-",
                 "Лекция + Семинар"]
                 
time_of_class = ["7.45-9.15",
                 "9.25-10.55",
                 "11.15-12.45",
                 "12.55-14.25",
                 "14.35-16.05",
                 "16.25-17.55",
                 "18.00-19.30",
                 "19.35-21.05"]
 
date_ranges = [
    {"start": "2023-10-09", "end": "2023-10-15", "type": "Числитель"},
    {"start": "2023-10-16", "end": "2023-10-23", "type": "Знаменатель"},
    {"start": "2023-10-24", "end": "2023-10-31", "type": "Числитель"},
    # ... и так далее
]

def format_schedule(df, current_week_type):
    response = ""
    for day in df["День"].unique():
        if current_week_type == "Числитель":
            day_schedule = df[(df["День"] == day) & ((df["Числитель?"] == 1) | (df["Числитель?"] == 2))]
        else:  # Знаменатель
            day_schedule = df[(df["День"] == day) & ((df["Числитель?"] == 0) | (df["Числитель?"] == 2))]

        if not day_schedule.empty:  # Если для этого дня есть пары
            response += f"📅 *{days[day - 1]}*:\n"
            for _, row in day_schedule.iterrows():
                response += f"| Пара №{row['Номер пары']} ({time_of_class[row['Номер пары'] - 1]}): {row['Предмет']}\n"
                response += f"| Аудитория: {row['Аудитория']}\n"
                response += f"| {row['Должность']} {row['Преподаватель']}\n"
                response += f"| Вид пары: {type_of_class[row['Вид пары']]}\n"
                response += "––––––––––––––\n"
            response += "\n"
    return response


def get_current_week_type(date_ranges):
    today = datetime.date.today()
    for range_ in date_ranges:
        start = datetime.datetime.strptime(range_["start"], "%Y-%m-%d").date()
        end = datetime.datetime.strptime(range_["end"], "%Y-%m-%d").date()
        if start <= today <= end:
            return range_["type"]
    return None  # Если текущая дата не входит ни в один из диапазонов

                 
def get_last_shown_date(user_id):
    cursor.execute("SELECT last_shown_date FROM users WHERE user_id = %s", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

def update_last_shown_date(user_id, date):
    cursor.execute("UPDATE users SET last_shown_date = %s WHERE user_id = %s", (date, user_id))
    connection.commit()

@bot.callback_query_handler(func=lambda call: call.data.startswith("show_schedule_"))
def show_schedule(call):
    faculty = call.data.split("_")[3]
    group = call.data.split("_")[2]
    schedule_path = os.path.join(os.getcwd(), f"{faculty}\{group}.xlsx")

    last_date = get_last_shown_date(call.from_user.id)
    today = datetime.date.today()

    if last_date != today:
        try:
            df = pd.read_excel(schedule_path)
            current_week_type = get_current_week_type(date_ranges)
            response = format_schedule(df, current_week_type)
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text="Изменить данные", callback_data="change_data"))
            markup.add(types.InlineKeyboardButton(text="Обновить расписание", callback_data=f"show_schedule_{group}_{faculty}"))
            
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=response, reply_markup=markup, parse_mode='Markdown')
            
            # Обновление даты последнего показа
            update_last_shown_date(call.from_user.id, today)
            
        except Exception as e:
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text="Изменить данные", callback_data="change_data"))
            bot.send_message(call.message.chat.id, f"Ошибка при загрузке расписания для группы {faculty} {group}. Причина: {e}. Пожалуйста, попробуйте позже.", reply_markup=markup)
    else:
        return

@bot.callback_query_handler(func=lambda call: call.data == "change_data")
def change_data(call):
    markup = types.InlineKeyboardMarkup()
    for faculty in DATA_HIERARCHY.keys():
        markup.add(types.InlineKeyboardButton(text=faculty, callback_data=f"faculty_{faculty}"))
    
    # Обновляем запись в базе данных, устанавливая все поля кроме user_id в NULL или аналогичные начальные значения
    try:
        cursor.execute("UPDATE users SET faculty = NULL, form_of_education = NULL, course = NULL, group_name = NULL, last_shown_date = NULL WHERE user_id = %s", (call.from_user.id,))
        connection.commit()
    except Exception as e:
        print(f"Error updating user data: {e}")  # или какой-то другой способ логирования

    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text="Выберите факультет:", reply_markup=markup)


bot.polling()