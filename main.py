import re
import time
import matplotlib.pyplot as plt
import numpy as np
from disnake import ApplicationCommandInteraction, File, Intents, NotFound, TextChannel, utils, Message
from disnake.ext.commands import InteractionBot, Param
from deta import Deta
from os import environ
from collections import Counter

plt.rcParams['axes.axisbelow'] = True
last_msg_db = Deta(environ['PROJECT_KEY']).Base('last_graph_msg')
bot = InteractionBot(intents=Intents.default())
cooldown_mins = 1
cooldown_secs = cooldown_mins * 60

@bot.event
async def on_ready():
    print("The bot is ready!")

@bot.slash_command()
async def plot(inter: ApplicationCommandInteraction):
    pass

@plot.sub_command(description='Make a plot of the amount of quotes per quotee. Pie chart by default')
async def make(
    inter: ApplicationCommandInteraction,
    chart_type: str = Param(description='Type of chart (default: horizontal_bar_chart)', choices=['pie_chart', 'horizontal_bar_chart', 'vertical_bar_chart'], default='horizontal_bar_chart'),
    query: str = Param(description='Query to find and sort by (default: None)', default='')
):
    # Defer response just in case
    await inter.response.defer(ephemeral=True)

    # Get from database
    await inter.edit_original_message('Checking database...')
    last_msg_stats = last_msg_db.fetch({"key": str(inter.guild.id)}).items
    if last_msg_stats != []:
        # Check if difference between now() and timestamp is >= 30 minutes
        last_msg_stats = last_msg_stats[0]
        time_diff = int(time.time()) - int(last_msg_stats['issue_time'])

        if time_diff < cooldown_secs:
            # If no, shout at user and return
            await inter.edit_original_message(
                f"<@!{last_msg_stats['issuer_id']}> already made a graph recently.\nThe link to that message is {last_msg_stats['msg_link']}\nYou must wait **{(cooldown_secs - time_diff) // 60}** more minutes before using this command."
            )
            return

    # Get the quotes channel
    await inter.edit_original_message('Fetching quotes...')
    quotes_channel = utils.find(lambda channel: isinstance(channel, TextChannel) and channel.name == 'quotes', await inter.guild.fetch_channels())
    # If channel no exist, shout at user and return
    if quotes_channel is None:
        await inter.edit_original_message('No quotes channel found. The fuck?')
        return
    # Get all quotes
    quotes = await quotes_channel.history(limit=None).flatten()
    # Filter by query
    if query != '':
        def query_filter(msg: Message):
            stripped_quote = re.search(r'"(.+)"', msg.content)
            if stripped_quote is None:
                return False
            stripped_quote = stripped_quote.group(1)
            return True if query in stripped_quote else False
        
        quotes = list(filter(query_filter, quotes))
        
        if quotes == []:
            await inter.edit_original_message('No quotes matched your query! Sorry!')
            return

    # Map list[Message] to list of quotee IDs
    quotee_ids: list[str] = []
    for msg in quotes:
        match = re.findall(r'<@!?(\d+)>', msg.content)
        if match != []:
            quotee_id = match[-1]
            quotee_ids.append(quotee_id)

    # Make a counter out of it
    quotee_id_counts = Counter(quotee_ids)
    
    # others_count = 0
    # quotee_id_counts = {}
    # for key in unfiltered_quotee_id_counts:
    #     if unfiltered_quotee_id_counts[key] < 10:
    #         # try:
    #         #     unfiltered_quotee_id_counts['Others'] += unfiltered_quotee_id_counts[key]
    #         # except KeyError:
    #         #     unfiltered_quotee_id_counts['Others'] = unfiltered_quotee_id_counts[key]
    #         # del unfiltered_quotee_id_counts[key]
    #         others_count += unfiltered_quotee_id_counts[key]
    #     else:
    #         quotee_id_counts[key] = unfiltered_quotee_id_counts[key]

    # Turn the counter IDs to usernames
    # quotee_counts = {str(await bot.fetch_user(id)): count for (id, count) in quotee_id_counts.items()}

    quotee_counts = {}
    for id, count in quotee_id_counts.items():
        try:
            user = await bot.fetch_user(id)
        except NotFound:
            continue
        quotee_counts[str(user)] = count

    # quotee_counts['Others'] = others_count
    quotee_counts = dict(sorted(quotee_counts.items(), key=lambda item: item[1]))

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
    graph_msg = await inter.channel.send(file=File('./graph.jpg'))

    # Update database
    last_msg_db.put({
        "key": str(inter.guild.id),
        "issuer_id": str(inter.author.id),
        "chart_type": chart_type,
        "query": query,
        "issue_time": int(time.time()),
        "msg_link": graph_msg.jump_url
    })

bot.run(environ['BOT_TOKEN'])
