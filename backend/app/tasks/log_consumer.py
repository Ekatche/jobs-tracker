import pika
import json
import logging
import os
import time
import pathlib
from datetime import datetime
from dotenv import load_dotenv

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
dotenv_path = pathlib.Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Configuration RabbitMQ
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")


def callback(ch, method, properties, body):
    """Fonction appelée à chaque message reçu"""
    try:
        message = json.loads(body)
        level = message.get("level", "INFO")
        log_message = message.get("message", "Aucun message")
        timestamp = message.get("timestamp", datetime.now().isoformat())

        # Formatage du message de log
        formatted_message = f"[{timestamp}] {level}: {log_message}"

        # Affichage dans les logs
        if level == "ERROR":
            logger.error(formatted_message)
        else:
            logger.info(formatted_message)

        # Détails supplémentaires
        if "count" in message:
            logger.info(f"Nombre de candidatures traitées: {message['count']}")

        if "archived_ids" in message and message["archived_ids"]:
            logger.info(
                f"ID des candidatures archivées: {', '.join(message['archived_ids'][:5])}"
                + (
                    f" ... et {len(message['archived_ids']) - 5} autres"
                    if len(message["archived_ids"]) > 5
                    else ""
                )
            )

        # Accusé de réception
        ch.basic_ack(delivery_tag=method.delivery_tag)

    except json.JSONDecodeError:
        logger.error(f"Message invalide: {body}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as e:
        logger.error(f"Erreur lors du traitement du message: {str(e)}")
        ch.basic_ack(delivery_tag=method.delivery_tag)


def start_consumer():
    """Démarrer le consommateur de messages"""
    # Créer le dossier de logs s'il n'existe pas
    os.makedirs("/app/logs", exist_ok=True)

    # Ajouter un fichier log pour les messages
    log_file = f"/app/logs/archive_logs_{datetime.now().strftime('%Y%m%d')}.log"
    try:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(file_handler)
        logger.info(f"Logs enregistrés dans {log_file}")
    except Exception as e:
        logger.error(f"Erreur lors de la création du fichier de log: {str(e)}")

    connection = None
    retry_count = 0
    max_retries = 20

    while retry_count < max_retries:
        try:
            logger.info(
                f"Tentative de connexion à RabbitMQ ({retry_count+1}/{max_retries})..."
            )
            credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    credentials=credentials,
                    heartbeat=600,
                    connection_attempts=3,
                    retry_delay=5,
                )
            )
            channel = connection.channel()

            # Déclarer la queue (durable=True pour persistance)
            channel.queue_declare(queue="job_tracker_archive_logs", durable=True)

            # Configuration du prefetch pour équilibrer la charge
            channel.basic_qos(prefetch_count=1)

            # Configuration du callback
            channel.basic_consume(
                queue="job_tracker_archive_logs", on_message_callback=callback
            )

            logger.info("Consommateur de logs démarré. Pour quitter: CTRL+C")
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError:
            retry_count += 1
            wait_time = min(30, 2**retry_count)  # Backoff exponentiel
            logger.error(
                f"Erreur de connexion à RabbitMQ. Nouvelle tentative dans {wait_time} secondes..."
            )
            time.sleep(wait_time)
        except KeyboardInterrupt:
            if connection and connection.is_open:
                connection.close()
            logger.info("Consommateur arrêté")
            break
        except Exception as e:
            logger.error(f"Erreur inattendue: {str(e)}")
            retry_count += 1
            time.sleep(5)
            if connection and connection.is_open:
                connection.close()


if __name__ == "__main__":
    start_consumer()
