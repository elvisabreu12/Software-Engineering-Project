from database import SessionLocal
import models

# Test database connection and model queries print an OK or FAIL message for each model
db = SessionLocal()
for model in [models.Role, models.User, models.Category, models.Ticket,
              models.Comment, models.InternalComment, models.LoginAttempt]:
    try:
        count = db.query(model).count()
        print("OK  ", model.__name__, count, "rows")
    except Exception as e:
        print("FAIL", model.__name__, "->", str(e).splitlines()[0])
        db.rollback()# reset the session so the next model can still be tested
db.close()