from utils.bot import Bot
#from utils.keep_alive import keep_alive
import os
from dotenv import load_dotenv


load_dotenv()


def main():
  bot = Bot()
  TOKEN = os.environ.get('TOKEN')
  #keep_alive()
  bot.run(TOKEN)

if __name__ == "__main__":
  main()


