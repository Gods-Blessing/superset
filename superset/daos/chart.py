# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
# pylint: disable=arguments-renamed
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.exc import SQLAlchemyError

from superset.charts.filters import ChartFilter
from superset.daos.base import BaseDAO
from superset.extensions import db
from superset.models.core import FavStar, FavStarClassName
from superset.models.slice import Slice
from superset.utils.core import get_iterable, get_user_id

if TYPE_CHECKING:
    from superset.connectors.base.models import BaseDatasource

logger = logging.getLogger(__name__)


class ChartDAO(BaseDAO[Slice]):
    base_filter = ChartFilter

    @classmethod
    def delete(cls, items: Slice | list[Slice], commit: bool = True) -> None:
        item_ids = [item.id for item in get_iterable(items)]
        # bulk delete, first delete related data
        for item in get_iterable(items):
            item.owners = []
            item.dashboards = []
            db.session.merge(item)
        # bulk delete itself
        try:
            db.session.query(Slice).filter(Slice.id.in_(item_ids)).delete(
                synchronize_session="fetch"
            )
            if commit:
                db.session.commit()
        except SQLAlchemyError as ex:
            db.session.rollback()
            raise ex

    @staticmethod
    def save(slc: Slice, commit: bool = True) -> None:
        db.session.add(slc)
        if commit:
            db.session.commit()

    @staticmethod
    def overwrite(slc: Slice, commit: bool = True) -> None:
        db.session.merge(slc)
        if commit:
            db.session.commit()

    @staticmethod
    def favorited_ids(charts: list[Slice]) -> list[FavStar]:
        ids = [chart.id for chart in charts]
        return [
            star.obj_id
            for star in db.session.query(FavStar.obj_id)
            .filter(
                FavStar.class_name == FavStarClassName.CHART,
                FavStar.obj_id.in_(ids),
                FavStar.user_id == get_user_id(),
            )
            .all()
        ]

    @staticmethod
    def add_favorite(chart: Slice) -> None:
        ids = ChartDAO.favorited_ids([chart])
        if chart.id not in ids:
            db.session.add(
                FavStar(
                    class_name=FavStarClassName.CHART,
                    obj_id=chart.id,
                    user_id=get_user_id(),
                    dttm=datetime.now(),
                )
            )
            db.session.commit()

    @staticmethod
    def remove_favorite(chart: Slice) -> None:
        fav = (
            db.session.query(FavStar)
            .filter(
                FavStar.class_name == FavStarClassName.CHART,
                FavStar.obj_id == chart.id,
                FavStar.user_id == get_user_id(),
            )
            .one_or_none()
        )
        if fav:
            db.session.delete(fav)
            db.session.commit()
