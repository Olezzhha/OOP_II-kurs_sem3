

import logging
import time
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler


class TimeTrackerBot:

    def __init__(self):
        self.user_timers = {}
        self.user_statistics = {}

        # логирование
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s', level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        self.setup_handlers()

    def setup_handlers(self):
        # команды
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("end", self.end))
        self.application.add_handler(CommandHandler("statistics", self.statistics))

        # текстовые сообщения
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_task))
        self.application.add_handler(CallbackQueryHandler(self.handle_statistics_period, pattern='^1|2|3'))
        self.application.add_handler(CallbackQueryHandler(self.handle_next_action, pattern='^(new_timer|view_statistics|continue)'))
        self.application.add_handler(CallbackQueryHandler(self.handle_rest_response, pattern='^(yes|no)'))

    # запуск
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        welcome_message = (
            "Привет! Я ваш помощник для отслеживания времени.\n"
            "Вот что я умею:\n"
            "/start - Вывести приветствие и начать работу с ботом.\n"
            "/end - Остановить таймер.\n"
            "/statistics - Показать статистику за день, неделю или месяц с суммарным подсчетом времени.\n"
            "\n*Kогда пройдет пол часа, я напомню вам отвлечься и сделать зарядку!*\n"
            "Просто напишите дело, которое вы собираетесь делать, и я начну отсчет времени!\n\n"
            "Напишите название задачи, которую будете выполнять:"
        )
        await update.message.reply_text(welcome_message)

        # вывод инфы что таймер запущен
    async def handle_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_chat.id
        task = update.message.text

        if user_id in self.user_timers:
            await update.message.reply_text('Вы уже запустили таймер. Используйте команду /end, чтобы завершить его')
            return

        await update.message.reply_text(f'Запускаю таймер для: "{task}". Нажмите /end, чтобы остановить таймер')
        self.user_timers[user_id] = {'task': task, 'start_time': time.time(), 'paused_time': 0, 'is_paused': False}

        # Инициализация статистики, если ее нет
        if user_id not in self.user_statistics:
            self.user_statistics[user_id] = {}

        # Штука напоминаний об отдыхе
        asyncio.create_task(self.remind_to_rest(user_id, context))

    # напоминалка что надо отдохнуть
    async def remind_to_rest(self, user_id, context):
        while user_id in self.user_timers:
            await asyncio.sleep(30)  # Ждем 30 минут
            if user_id in self.user_timers and not self.user_timers[user_id]['is_paused']:
                keyboard = [
                    [InlineKeyboardButton("Да", callback_data='yes')],
                    [InlineKeyboardButton("Нет", callback_data='no')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await context.bot.send_message(
                    chat_id=user_id,
                    text="Время для отдыха! Хотите сделать зарядку?",
                    reply_markup=reply_markup
                )

    # хэндл для напоминания об отдыхе
    async def handle_rest_response(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if user_id not in self.user_timers:
            await query.message.reply_text("У вас нет активного таймера")
            return

        if query.data == 'yes':
            await context.bot.send_message(
                chat_id=user_id,
                text="Подсчет времени приостановлен\nВот ссылки на зарядки:\n"
                     "0. Хехе: [Ссылка](https://ru.pinterest.com/pin/603412050108089537/)\n"
                     "1. Зарядка для глаз: [Ссылка](https://msp.midural.ru/upload/gallery/2018/10/11/mxGST.jpg)\n"
                     "2. Разминка на стуле: [Ссылка](https://thumbs.dreamstime.com/z/office-exercise-set-body-workout-office-office-exercise-set-body-workout-office-worker-neck-shoulder-back-stretch-140991072.jpg)",
                parse_mode='Markdown'
            )

            self.user_timers[user_id]['is_paused'] = True
            self.user_timers[user_id]['paused_time'] = time.time()

            keyboard = [[InlineKeyboardButton("Продолжить", callback_data='continue')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.send_message(
                chat_id=user_id,
                text="Нажмите кнопку ниже, чтобы продолжить таймер",
                reply_markup=reply_markup
            )
        elif query.data == 'no':
            await context.bot.send_message(
                chat_id=user_id,
                text="Хорошо, продолжаем работу"
            )

        await context.bot.send_message(
            chat_id=user_id,
            text="Нажмите или напишите /end, чтобы остановить таймер"
        )

        # ф-ия, чтобы продолжить работу после остановки во время отдыха
    async def handle_continue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if user_id in self.user_timers and self.user_timers[user_id]['is_paused']:
            paused_duration = time.time() - self.user_timers[user_id]['paused_time']
            self.user_timers[user_id]['start_time'] += paused_duration
            self.user_timers[user_id]['is_paused'] = False
            await context.bot.send_message(
                chat_id=user_id,
                text="Таймер продолжен! Успехов в работе!"
            )

        await context.bot.send_message(
            chat_id=user_id,
            text="Нажмите /end, чтобы остановить подсчет времени"
        )

        # конец счетчика времени
    async def end(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_chat.id

        if user_id not in self.user_timers:
            await update.message.reply_text('У вас нет активного таймера. Просто напишите название дела и таймер запустится!')
            return

        elapsed_time = self.calculate_elapsed_time(user_id)

        task = self.user_timers[user_id]['task']
        self.record_statistics(user_id, task, elapsed_time)

        await update.message.reply_text(
            f'Таймер для "{task}" остановлен. Вы потратили {self.format_time(elapsed_time)}'
        )
         #обновить таймер
        del self.user_timers[user_id]

        keyboard = [
            [InlineKeyboardButton("Начать новую задачу", callback_data='new_timer')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Что вы хотите сделать дальше? \n\n/statistics - Показать статистику\n", reply_markup=reply_markup)

     #считаем паузу, чтобы она не шла в суммарное время
    def calculate_elapsed_time(self, user_id):
        return (self.user_timers[user_id]['paused_time'] - self.user_timers[user_id]['start_time']
                if self.user_timers[user_id]['is_paused']
                else time.time() - self.user_timers[user_id]['start_time'])

    def record_statistics(self, user_id, task, elapsed_time):
        if task not in self.user_statistics[user_id]:
            self.user_statistics[user_id][task] = []
        self.user_statistics[user_id][task].append((time.time(), elapsed_time))

      #изначально тоже из статистика, но так без повторения кода
    def format_time(self, elapsed_time):
        hours, remainder = divmod(int(elapsed_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        seconds = round(seconds, 1)
        return f"{hours} часов, {minutes} минут и {seconds} секунд"

    # стата по времени
    async def statistics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_chat.id

        if user_id not in self.user_statistics or not self.user_statistics[user_id]:
            await update.message.reply_text('У вас нет статистики. Начните работу и я покажу сколько времени вы потратили')
            return

        keyboard = [
            [InlineKeyboardButton("День", callback_data='1'),
             InlineKeyboardButton("Неделя", callback_data='2'),
             InlineKeyboardButton("Месяц", callback_data='3')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("Выберите период для просмотра статистики:", reply_markup=reply_markup)

    # хэндл для статы
    async def handle_statistics_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        period = query.data
        time_limit = self.get_time_limit(period)

        stats_message = f'Статистика за выбранный период:\n'
        total_time = 0

        for task, records in self.user_statistics[user_id].items():
            task_time = sum(elapsed for timestamp, elapsed in records if datetime.fromtimestamp(timestamp) >= time_limit)
            if task_time > 0:
                total_time += task_time
                task_dates_str = self.get_task_dates(records, time_limit)
                stats_message += f'• {task}: {self.format_time(task_time)} (дата: {task_dates_str})\n'

        stats_message += f'\nОбщее время: {self.format_time(total_time)}'
        await query.message.reply_text(stats_message)

        await self.ask_next_action(query.message)


     #Добавила: время, чтобы в нули начинался новый день
    def get_time_limit(self, period):
        if period == '1':
            return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == '2':
            today = datetime.now()
            return (today - timedelta(days=today.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == '3':
            return datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def get_task_dates(self, records, time_limit):
        return ', '.join(datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S') for timestamp, _ in records if datetime.fromtimestamp(timestamp) >= time_limit)


       #запрос следующего действия
    async def ask_next_action(self, message):
        keyboard = [[InlineKeyboardButton("Запустить новый таймер", callback_data='new_timer')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(
            "Вы хотите работать дальше или еще раз показать статистику? \n\n/statistics - Показать статистику\n",
            reply_markup=reply_markup)

       # хэндл следующего запроса
    async def handle_next_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id

        if query.data == 'new_timer':
            await query.message.reply_text("Пожалуйста, введите дело, для которого вы хотите запустить таймер.")
            return
        elif query.data == 'view_statistics':
            await self.statistics(query.message, context)
        elif query.data == 'end':
            await self.end(query.message, context)
        elif query.data == 'continue':
            await self.handle_continue(update, context)

    def run(self):
        # Запуск бота
        self.application.run_polling()


if __name__ == '__main__':
    bot = TimeTrackerBot()
    bot.run()
