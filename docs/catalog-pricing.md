# Catalog pricing notes

Last reviewed: 2026-09-01

Persian Shop's starter catalog contains 65 products in seven categories. Prices are retail
estimates in Iranian toman, rounded to customer-friendly amounts after comparing several active
Iranian providers. They are intentionally independent of any single supplier and should be
reviewed periodically because exchange rates and provider capacity change.

## Reference providers

- Instagram: [Followeran](https://followeran.com/fa/service/instagram/),
  [Digi Members](https://www.digi-members.com/buy-iranian-followers/), and
  [Cafe Majazi](https://cafemajazi.net/)
- Telegram: [Digi Members](https://www.digi-members.com/),
  [Shiraz Social](https://shirazsocial.com/telegram-group-member/), and
  [DrMagic](https://drmagic.ir/buy-telegram-post-views)
- TikTok: [Followeran](https://followeran.ir/service/buy-tiktok-likes/),
  [Shiraz Social](https://shirazsocial.com/tiktok-follower/), and
  [DrMagic](https://drmagic.ir/buy-tiktok-followers)
- YouTube: [KharidView](https://www.kharidview.ir/youtube-views/),
  [Shiraz Social](https://shirazsocial.com/youtube-subscribers/), and
  [ArzanPanel Iran](https://www.arzanpanel-iran.com/subscribe-youtube/)
- AI subscriptions: [AiCard](https://aicard.ir/),
  [Iranicard](https://www.iranicard.ir/payments/accounts/artificial-intelligence/), and
  [License Market](https://license-market.ir/product/ChatGPT-Plus)
- Premium subscriptions: [MarketPolo](https://marketpolo.ir/product/telegram-premium/),
  [License Market](https://license-market.ir/product/CapCut), and
  [Iran Spotify](https://spotifyy.ir/)

## Operating notes

- Prices stored by the bot are integer toman values.
- Social-media services only request a public profile, channel, post, or video URL. Passwords are
  never required.
- Account activations tell customers not to send passwords in the bot. Support should coordinate
  any provider-specific activation separately.
- Product seeding is idempotent: an existing product is not duplicated or overwritten on restart.
- Online payments remain disabled until the payment integration is explicitly reviewed and enabled.
