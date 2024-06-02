from typing import Tuple
from weaviate import Client
from weaviate.util import generate_uuid5
from src.db.schema import article_class
from ..util.config import weaviate_config

class WeaviateFacade:
    """Facade for the Weaviate client
    todo: make a singleton
    """
    def __init__(self, recreate_schema: bool = False):
        self._client = Client(**weaviate_config)
        self.query = self._client.query
        
        if recreate_schema or not self.check_article_class_schema():
            self._setup(article_class)
        
    def check_article_class_schema(self):
        try:
            self._client.schema.get("Article")
            print("Schema for 'Article' class exists.")
            return True
        except Exception as e:
            print("Schema for 'Article' class does not exist.")
            return False
        
    def _setup(self, article_class) -> None:
        """Remove the current schema and create a new one"""
        self._client.schema.delete_class(article_class)
        self._client.schema.create_class(article_class)
        print(f'Class {article_class} was successfully re-created')

    def upload_data(self, data, data_type) -> None:
        """
        Upload the data to the db
        For each record, reproducible uuid is generated so the same entries won't be added again
        """
        with self._client.batch(
                batch_size=200,
                num_workers=2
        ) as batch:
            for idx, record in enumerate(data):
                class_name, class_object = self.mapper(data_type, record)
                batch.add_data_object(
                    class_object,
                    class_name,
                    uuid=generate_uuid5(class_object)
                )
                print(f'imported {type} {idx + 1}')

        print(f'Total of {len(data)} records were uploaded')

    def delete_data(self, articles, class_name) -> None:
        """
        Delete the articles from the db
        """
        with self._client.batch(
                batch_size=200,
                num_workers=2
        ) as batch:
            for idx, record in enumerate(articles):
                batch.delete_objects(
                    class_name=class_name,
                    where={
                        "operator": "Equal",
                        "path": ["last_edited"],
                        "valueDate": record["last_edited"]
                    },
                    dry_run=False
                )
                print(f'deleted {type} {idx + 1}')

        print(f'Total of {len(articles)} records were deleted')
    
    def search_articles(self, query: str, limit=5) -> dict:
        return self._client.query.get("Article", ["title", "text", "article_id"]) \
            .with_near_text({"concepts": query}) \
            .with_where({"path": ["language"],"operator": "Equal","valueText": "en",}) \
            .with_limit(limit) \
            .do()

   
    @staticmethod
    def mapper(data_type, record) -> Tuple[str, dict]:
        """Mappings for uploading the data"""
        record_class = {
            'Article': article_class,
        }[data_type]

        class_name = record_class["class"]
        obj = {}

        for prop in record_class["properties"]:
            key = prop["name"]
            obj[key] = record[key]

        return class_name, obj
