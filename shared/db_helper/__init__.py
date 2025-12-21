from .helper import DBHelper

# canonical DB handles
db_config = DBHelper("db/config/config.db")
db_log    = DBHelper("db/log/log.db")
db_buffer = DBHelper("db/buffer/buffer.db")
