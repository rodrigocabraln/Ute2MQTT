"""Read-only authenticated access to UTE's quarter-hour load curve."""
from datetime import date, timedelta
import requests
from .normalize import normalize_quarters

BASE = "https://autoservicio.ute.com.uy/SelfService/SSvcController"


def fetch(options: dict, context: dict, first: date, last: date) -> dict[str, float]:
    """Fetch inclusive local dates in batches of at most thirty days."""
    if first > last:
        raise ValueError("Start date must precede end date")
    with requests.Session() as session:
        session.get(BASE + "/login", timeout=30).raise_for_status()
        login = session.post(BASE + "/authenticate", data={
            "userId": options["document"], "password": options["password"]}, timeout=30)
        login.raise_for_status()
        if 'name="password"' in login.text:
            raise ValueError("UTE rejected portal authentication")
        session.get(BASE + "/cmvisualizarcurvadecarga", params={
            "saId": context["serviceAgreementId"],
            "spId": context["servicePointId"]}, timeout=30).raise_for_status()
        result = {}
        cursor = first
        while cursor <= last:
            end = min(cursor + timedelta(days=29), last)
            parameters = {
                "psId": context["servicePointId"], "meterId": "",
                "fechaInicial": cursor.strftime("%d-%m-%Y"),
                "fechaFinal": end.strftime("%d-%m-%Y"),
                "agrupacion": "QH", "magnitudes": "IMPORT_ACTIVE_ENERGY",
            }
            query = {"graficas[0][name]": "CURVA_DE_CONSUMO"}
            query.update({f"graficas[0][parms][{key}]": value
                          for key, value in parameters.items()})
            response = session.get(BASE + "/cmgraficar", params=query,
                headers={"X-Requested-With": "XMLHttpRequest"}, timeout=60)
            response.raise_for_status()
            result.update(normalize_quarters(response.json(), cursor, end))
            cursor = end + timedelta(days=1)
        return result
