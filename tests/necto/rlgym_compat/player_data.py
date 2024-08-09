from .physics_object import PhysicsObject


class PlayerData(object):
    car_id: int = -1
    team_num: int = -1
    is_demoed: bool = False
    on_ground: bool = False
    ball_touched: bool = False
    has_jump: bool = False
    has_flip: bool = False
    boost_amount: float = -1
    car_data: PhysicsObject = PhysicsObject()
    inverted_car_data: PhysicsObject = PhysicsObject()
