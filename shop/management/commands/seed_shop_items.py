from django.core.management.base import BaseCommand
from shop.models import Badge, ShopItem

class Command(BaseCommand):
    help = "Seed default shop items (badges + lootbox)."

    def handle(self, *args, **options):
        badges = [
            ("VIP", "VIP 玩家", "💎", 3),
            ("HOT", "火燙手感", "🔥", 2),
            ("SNIPER", "神射手", "🎯", 2),
            ("ROOKIE", "新秀", "🌱", 1),
        ]
        for code, name, emoji, rarity in badges:
            Badge.objects.update_or_create(code=code, defaults={"name": name, "emoji": emoji, "rarity": rarity})

        for code, name, emoji, rarity in badges:
            ShopItem.objects.update_or_create(
                code=f"BADGE_{code}",
                defaults={
                    "name": f"{emoji} 徽章：{name}",
                    "description": "購買後可在背包裝備（純美觀）。",
                    "price": 250 if rarity == 1 else 400 if rarity == 2 else 700,
                    "active": True,
                    "kind": "BADGE",
                    "payload": {"badge_code": code},
                },
            )

        ShopItem.objects.update_or_create(
            code="LOOTBOX_BASIC",
            defaults={
                "name": "🎁 戰利品箱（基礎）",
                "description": "開箱可獲得金幣或隨機徽章。",
                "price": 300,
                "active": True,
                "kind": "LOOT_BOX",
                "payload": {
                    "min_coins": 120,
                    "max_coins": 520,
                    "badge_chance": 0.35,
                    "badge_pool": ["ROOKIE", "HOT", "SNIPER", "VIP"],
                },
            },
        )

        self.stdout.write(self.style.SUCCESS("Seeded shop items OK."))
