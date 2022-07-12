import re
import time
import matplotlib.pyplot as plt
import numpy as np
import itertools
from disnake import ApplicationCommandInteraction, File, Intents, TextChannel, utils, Message
from disnake.ext.commands import InteractionBot, Param
from os import environ
from collections import Counter

plt.rcParams['axes.axisbelow'] = True
bot = InteractionBot(intents=Intents.default())
cooldown_mins = 30
cooldown_secs = cooldown_mins * 60
quotes_time_dict = {
    'quotes': None,
    'timestamp': None
}

@bot.event
async def on_ready():
    print("The bot is ready!")

@bot.slash_command()
async def plot(inter: ApplicationCommandInteraction):
    pass

@plot.sub_command(description='Make a plot of the amount of quotes per quotee. Horizontal bar chart by default')
async def make(
    inter: ApplicationCommandInteraction,
    chart_type: str = Param(description='Type of chart (default: horizontal_bar_chart)', choices=['pie_chart', 'horizontal_bar_chart', 'vertical_bar_chart'], default='horizontal_bar_chart'),
    query: str = Param(description='Query to find and sort by (default: None)', default='')
):
    # Defer response just in case
    await inter.response.defer(ephemeral=True)

    # Get the quotes channel
    await inter.edit_original_message('Fetching quotes...')

    if quotes_time_dict['quotes'] is None or quotes_time_dict['timestamp'] is None or (int(time.time()) - int(quotes_time_dict['timestamp'])) >= cooldown_secs:
        quotes_channel = utils.find(lambda channel: isinstance(channel, TextChannel) and channel.name == 'quotes', await inter.guild.fetch_channels())
        # If channel no exist, shout at user and return
        if quotes_channel is None:
            await inter.edit_original_message('No quotes channel found. The fuck?')
            return
        # Get all quotes
        quotes = await quotes_channel.history(limit=None).flatten()
        quotes_time_dict['quotes'] = quotes
        quotes_time_dict['timestamp'] = int(time.time())
    else:
        quotes = quotes_time_dict['quotes']

    # Filter by query
    if query != '':
        await inter.edit_original_message('Filtering by query...')
        def query_filter(msg: Message):
            if '\n' in msg.content:
                stripped_quote = re.findall(r':\s(.+)', msg.content)
                print(stripped_quote)
                if stripped_quote == []:
                    return False
                return True if query in ''.join(stripped_quote) else False
            else:
                stripped_quote = re.search(r'"(.+)"', msg.content)
                if stripped_quote is None:
                    return False
                stripped_quote = stripped_quote.group(1)
                print(stripped_quote)
                return True if query in stripped_quote else False
        
        quotes = list(filter(query_filter, quotes))
        
        if quotes == []:
            await inter.edit_original_message('No quotes matched your query! Sorry!')
            return

    await inter.edit_original_message('Cleaning up data...')
    mentions = [msg.mentions for msg in quotes]
    mentions = list(itertools.chain.from_iterable(mentions))
    mentions = [str(user) for user in mentions]

    # Make a counter out of it
    mention_counts = Counter(mentions)
    quotee_counts = dict(sorted(mention_counts.items(), key=lambda item: item[1]))

    await inter.edit_original_message('Rendering graph...')
    # Produce a graph, save as jpeg
    x = list(quotee_counts.keys())
    y = list(quotee_counts.values())

    if chart_type == 'horizontal_bar_chart':
        plt.barh(x, y)
        plt.grid(True)
    elif chart_type == 'pie_chart':
        plt.pie(y, labels=x, autopct=lambda ex: '{:.0f}'.format(ex*np.asarray(y, dtype=np.float32).sum()/100))
    elif chart_type == 'vertical_bar_chart':
        plt.xticks(rotation='vertical')
        plt.bar(x, y)
        plt.grid(True)

    plt.savefig('graph.jpg', dpi=300, bbox_inches='tight')

    await inter.edit_original_message('Done!')
    
    # Send message of graph
    await inter.channel.send(file=File('./graph.jpg'))
    plt.clf()

bot.run(environ['BOT_TOKEN'])
