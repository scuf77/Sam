from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class Cake:
    id: str
    name: str
    price: int  # в рублях
    description: str


CATALOG: List[Cake] = [
    Cake(
        id="honey",
        name="Медовик",
        price=1200,
        description="Классический медовый торт со сметанным кремом, 1 кг",
    ),
    Cake(
        id="napoleon",
        name="Наполеон",
        price=1500,
        description="Слоёный торт с заварным кремом, 1 кг",
    ),
    Cake(
        id="chocolate",
        name="Шоколадный",
        price=1300,
        description="Насыщенный шоколадный бисквит с ганашем, 1 кг",
    ),
    Cake(
        id="cheesecake",
        name="Чизкейк",
        price=1400,
        description="Нью-Йорк на песочной основе, 1 кг",
    ),
    Cake(
        id="carrot",
        name="Морковный",
        price=1250,
        description="Пряный морковный бисквит с крем-чизом, 1 кг",
    ),
]


def get_cake_by_id(cake_id: str) -> Optional[Cake]:
    for cake in CATALOG:
        if cake.id == cake_id:
            return cake
    return None
