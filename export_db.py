import os
import sys
import json
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# Build DATABASE_URL similar to app.py logic
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # allow passing as first CLI arg
    if len(sys.argv) > 1:
        DATABASE_URL = sys.argv[1]
    else:
        sys.stderr.write("ERROR: DATABASE_URL not set and not provided as argument.\n")
        sys.exit(1)

if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
elif DATABASE_URL.startswith('postgresql://') and '+psycopg' not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)

Base = declarative_base()

class PlanEntry(Base):
    __tablename__ = 'plan_entries'
    id = Column(Integer, primary_key=True)
    datum = Column(String(50), nullable=True)
    messdiener_text = Column(Text, nullable=True)
    art_uhrzeit = Column(String(100), nullable=True)

class Queue(Base):
    __tablename__ = 'queues'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)

class Enrollment(Base):
    __tablename__ = 'enrollments'
    id = Column(Integer, primary_key=True)
    person = Column(String(100), nullable=False)
    queue_id = Column(Integer, ForeignKey('queues.id', ondelete='CASCADE'), nullable=False)
    timestamp = Column(String(32), nullable=True)

    queue = relationship('Queue')


def main():
    try:
        engine = create_engine(DATABASE_URL, future=True)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = SessionLocal()
        try:
            plan = [["Datum", "Messdiener", "Art/Uhrzeit"]]
            for e in db.query(PlanEntry).order_by(PlanEntry.id.asc()).all():
                plan.append([e.datum or "", e.messdiener_text or "", e.art_uhrzeit or ""]) 

            queues = [["ID", "Name"]]
            for q in db.query(Queue).order_by(Queue.id.asc()).all():
                queues.append([str(q.id), q.name])

            enrollments = [["Person", "QueueID", "Timestamp"]]
            for en in db.query(Enrollment).order_by(Enrollment.id.asc()).all():
                enrollments.append([en.person, str(en.queue_id), en.timestamp or ""]) 

            state = {"plan": plan, "queues": queues, "enrollments": enrollments}
            json.dump(state, sys.stdout, ensure_ascii=False, indent=2)
            sys.stdout.write("\n")
        finally:
            db.close()
    except Exception as e:
        sys.stderr.write(f"Export failed: {e}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()

