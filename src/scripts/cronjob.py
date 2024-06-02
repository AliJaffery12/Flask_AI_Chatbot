from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from ..articles_operator import ArticlesOperator

def monitor_database():
    """
    This function is responsible for monitoring the database and updating it with new articles.
    """
    from application import application
    
    try:
        with application.app_context():
            print("Scheduled task started.")
            data_loader = ArticlesOperator()
            data_loader.sync_data()
            print("Scheduled task completed.")
    except Exception as e:
        print("Error in Weaviate update:", str(e))

        
database_scheduler = BackgroundScheduler()

database_scheduler.add_job(
    func=monitor_database,
    trigger=CronTrigger(hour=0, minute=0),
)