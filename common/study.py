import os
from datetime import timedelta

from dotenv import load_dotenv
from models import Action, User
from sqlalchemy.orm import sessionmaker

from common import utilities

load_dotenv("dev.env")

class Study():
    def __init__(self):
        engine = utilities.get_engine()
        self.sqlalchemy_session = sessionmaker(bind=engine)()
        self.redis_client = utilities.get_redis_client()
        self.role_name_to_obj = utilities.config[("test_" if os.getenv("mode") == "test" else "") + "study_roles"]

    def getUserStats(self, id):
        """
        return a users stats from their id
        """
        timepoint = f"daily_{utilities.get_day_start()}"
        rank_categories = utilities.get_rank_categories()
        user_sql_obj = (
            self.sqlalchemy_session.query(User).filter(User.id == id).first()
        )
        stats = utilities.get_time_interval_user_stats(
            self.redis_client, id, timepoint=timepoint
        )
        stats["average_per_day"] = utilities.round_num(
            stats["pastMonth"]["study_time"]
            / utilities.get_num_days_this_month()
        )

        stats["currentStreak"] = user_sql_obj.current_streak if user_sql_obj else 0
        stats["longestStreak"] = user_sql_obj.longest_streak if user_sql_obj else 0

        return stats

    def getUserRoleInfo(self, id):
        user_id = id
        rank_categories = utilities.get_rank_categories()

        hours_cur_month = utilities.get_redis_score(self.redis_client, rank_categories["monthly"], user_id)
        if not hours_cur_month:
            hours_cur_month = 0

        role, next_role, time_to_next_role = utilities.get_role_status(self.role_name_to_obj, hours_cur_month)

        return {
            'role': role,
            'next_role': next_role,
            'time_to_next_role': time_to_next_role
        }

    def get_neighbor_stats(self, time_interval, user_id):
        print(time_interval)

        timepoint = utilities.time_interval_to_timepoint(time_interval)
        sorted_set_name = timepoint

        rank = utilities.get_redis_rank(self.redis_client, sorted_set_name, user_id)
        rank -= 1  # Use 0 index
        id_with_score = self.get_info_from_leaderboard(sorted_set_name, rank - 5, rank + 5)

        return id_with_score

    def get_info_from_leaderboard(self, sorted_set_name, start=0, end=-1):
        if start < 0:
            start = 0

        id_li = [int(i) for i in self.redis_client.zrevrange(sorted_set_name, start, end)]
        id_with_score = []

        for neighbor_id in id_li:
            res = dict()
            res["discord_user_id"] = neighbor_id
            res["rank"] = utilities.get_redis_rank(self.redis_client, sorted_set_name, neighbor_id)
            res["study_time"] = utilities.get_redis_score(self.redis_client, sorted_set_name, neighbor_id)
            id_with_score.append(res)

        return id_with_score


    def getUserTimeSeries(self, id, time_interval):
        timeseries = utilities.get_user_timeseries(self.redis_client, id, time_interval)
        return timeseries

    def getLeaderboard(self, offset, limit, time_interval):
        timepoint = utilities.time_interval_to_timepoint(time_interval)
        start = offset
        end = offset + limit

        sorted_set_name = timepoint

        if start < 0:
            start = 0

        id_list = [
            int(i) for i in self.redis_client.zrevrange(sorted_set_name, start, end)
        ]
        id_with_score = []

        for neighbor_id in id_list:
            res = dict()
            res["discord_user_id"] = neighbor_id
            res["rank"] = utilities.get_redis_rank(
                self.redis_client, sorted_set_name, neighbor_id
            )
            res["study_time"] = utilities.get_redis_score(
                self.redis_client, sorted_set_name, neighbor_id
            )
            id_with_score.append(res)

        return id_with_score