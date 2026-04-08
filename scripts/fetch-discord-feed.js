#!/usr/bin/env node
/**
 * Fetches recent messages from the DocWorm Discord sharing channel
 * and writes a static JSON file for serving via GitHub Pages.
 *
 * Required env vars:
 *   DISCORD_BOT_TOKEN          — Bot token with Read Message History + View Channel
 *   DISCORD_SHARING_CHANNEL_ID — Channel ID of the #sharing channel
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const TOKEN = process.env.DISCORD_BOT_TOKEN;
const CHANNEL_ID = process.env.DISCORD_SHARING_CHANNEL_ID;
const OUT_DIR = path.join(__dirname, '..', 'dist-feed');
const OUT_FILE = path.join(OUT_DIR, 'discord-messages.json');
const MAX_CONTENT_LENGTH = 280;

if (!TOKEN || !CHANNEL_ID) {
  console.error('Missing DISCORD_BOT_TOKEN or DISCORD_SHARING_CHANNEL_ID');
  process.exit(1);
}

function discordGet(apiPath) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'discord.com',
      path: apiPath,
      method: 'GET',
      headers: {
        'Authorization': `Bot ${TOKEN}`,
        'Content-Type': 'application/json',
        'User-Agent': 'DocWormFeedBot/1.0'
      }
    };
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode >= 400) {
          reject(new Error(`Discord API error ${res.statusCode}: ${data}`));
        } else {
          try { resolve(JSON.parse(data)); }
          catch (e) { reject(new Error(`JSON parse error: ${e.message}`)); }
        }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

function shorten(text, max) {
  if (!text || text.length <= max) return text || '';
  return text.slice(0, max - 1) + '…';
}

async function main() {
  console.log(`Fetching channel ${CHANNEL_ID} metadata…`);
  const channelInfo = await discordGet(`/api/v10/channels/${CHANNEL_ID}`);
  const guildId = channelInfo.guild_id;
  if (!guildId) {
    console.warn('No guild_id found — message links will fall back to @me');
  }

  console.log(`Fetching messages from channel ${CHANNEL_ID}…`);
  const raw = await discordGet(`/api/v10/channels/${CHANNEL_ID}/messages?limit=50`);

  const messages = raw
    .filter(m => m.type === 0 && !m.author.bot && m.content && m.content.trim().length > 0)
    .map(m => ({
      id: m.id,
      author: m.author.global_name || m.author.username,
      avatar: m.author.avatar
        ? `https://cdn.discordapp.com/avatars/${m.author.id}/${m.author.avatar}.png?size=64`
        : `https://cdn.discordapp.com/embed/avatars/${parseInt(m.author.discriminator || '0') % 5}.png`,
      content: m.content,
      contentShort: shorten(m.content, MAX_CONTENT_LENGTH),
      timestamp: m.timestamp,
      link: `https://discord.com/channels/${guildId || '@me'}/${CHANNEL_ID}/${m.id}`,
      attachmentCount: (m.attachments || []).length,
      reactionCount: (m.reactions || []).reduce((s, r) => s + (r.count || 0), 0)
    }));

  const output = {
    updated: new Date().toISOString(),
    channel: 'sharing',
    messages
  };

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(OUT_FILE, JSON.stringify(output, null, 2), 'utf8');
  console.log(`Wrote ${messages.length} messages to ${OUT_FILE}`);
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
