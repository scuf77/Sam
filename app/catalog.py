from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Cake:
    id: str
    name: str
    price: int  # в рублях
    description: str
    photo_url: str  # URL фотографии торта


CATALOG: List[Cake] = [
    Cake(
        id="honey",
        name="Медовик",
        price=1200,
        description="Классический медовый торт со сметанным кремом, 1 кг",
        photo_url="https://images.unsplash.com/photo-1578985545062-69928b1d9587?w=800&h=600&fit=crop&crop=center"
    ),
    Cake(
        id="napoleon",
        name="Наполеон",
        price=1500,
        description="Слоёный торт с заварным кремом, 1 кг",
        photo_url="https://images.unsplash.com/photo-1565958011703-44f9829ba187?w=800&h=600&fit=crop&crop=center"
    ),
    Cake(
        id="chocolate",
        name="Шоколадный",
        price=1300,
        description="Насыщенный шоколадный бисквит с ганашем, 1 кг",
        photo_url="https://images.unsplash.com/photo-1606313564200-e75d5e30476c?w=800&h=600&fit=crop&crop=center"
    ),
    Cake(
        id="cheesecake",
        name="Чизкейк",
        price=1400,
        description="Нью-Йорк на песочной основе, 1 кг",
        photo_url="https://images.unsplash.com/photo-1533134242443-d4fd215305ad?w=800&h=600&fit=crop&crop=center"
    ),
    Cake(
        id="carrot",
        name="Морковный",
        price=1250,
        description="Пряный морковный бисквит с крем-чизом, 1 кг",
        photo_url="https://images.unsplash.com/photo-1621303837174-89787a7d4729?w=800&h=600&fit=crop&crop=center"
    ),
]


def get_cake_by_id(cake_id: str) -> Optional[Cake]:
    for cake in CATALOG:
        if cake.id == cake_id:
            return cake
    return None
