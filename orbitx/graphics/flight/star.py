from typing import Optional

import vpython

from orbitx.data_structures.entity import Entity
from orbitx.data_structures.space import PhysicsState
from orbitx.graphics.flight.planet import Planet
from orbitx.graphics.flight.threedeeobj import ThreeDeeObj


class Star(Planet):

    def _create_obj(
            self, entity: Entity, origin: Entity,
            texture: Optional[str]) -> vpython.sphere:
        obj = super()._create_obj(entity, origin, texture)
        obj.emissive = True  # The sun glows!
        self._light = vpython.local_light(pos=obj.pos)
        return obj

    def relevant_range(self):
        return self._obj.radius * 15000

    def _update_obj(self, entity: Entity,
                    state: PhysicsState, origin: Entity) -> None:
        ThreeDeeObj._update_obj(self, entity, state, origin)
        # Also make sure to change the position of the light
        self._light.pos = self._obj.pos
