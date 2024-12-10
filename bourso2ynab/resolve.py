from actual.database import Transactions as ActualTransaction

from bourso2ynab.actual import convert_transaction_from_actual
from bourso2ynab.transaction import Transaction


def resolve_transactions(
    remote_transactions: list[Transaction | ActualTransaction],
    local_transactions: list[Transaction],
) -> dict[str, list[Transaction]]:
    """Reconciles two lists of transactions to identify missing entries on both sides.

    Compares remote (YNAB, Actual,...) and local transaction lists to find transactions
    that exist in one list but not the other. Remote transactions can be either
    Transaction or ActualTransaction type and will be converted as needed.
    YNAB transactions are currently not supported.

    Args:
        remote_transactions: List of transactions from the remote source (YNAB,
            Actual...)
        local_transactions: List of transactions from the local source.

    Returns:
        Dictionary with two keys:
            - missing_from_local: Transactions present in remote but not in local
            - missing_from_remote: Transactions present in local but not in remote

    Example:
        >>> remote = [Transaction(date=1, amount=100), Transaction(date=2, amount=200)]
        >>> local = [Transaction(date=1, amount=100)]
        >>> resolve_transactions(remote, local)
        {
            'missing_from_local': [Transaction(date=2, amount=200)],
            'missing_from_remote': []
        }
    """
    # Converting the remote transactions to be all from type "Transaction".
    safe_remote_transactions: list[Transaction] = [
        convert_transaction_from_actual(t) if isinstance(t, ActualTransaction) else t
        for t in remote_transactions
    ]

    # Sorting transactions by date, amount and payee
    safe_remote_transactions = sorted(safe_remote_transactions)
    safe_local_transactions = sorted(local_transactions)

    # Trivial cases: when one of the 2 lists is empty.
    if len(safe_remote_transactions) == 0:
        return {
            "missing_from_local": [],
            "missing_from_remote": safe_local_transactions,
        }
    if len(safe_local_transactions) == 0:
        return {
            "missing_from_local": safe_remote_transactions,
            "missing_from_remote": [],
        }

    # We will keep an index for both remote and local and progress chronologically.
    i_remote, i_local = 0, 0
    missing_transactions = {"missing_from_local": [], "missing_from_remote": []}
    while (i_remote < len(safe_remote_transactions)) and (
        i_local < len(safe_local_transactions)
    ):
        t_remote = safe_remote_transactions[i_remote]
        t_local = safe_local_transactions[i_local]

        if t_remote == t_local:
            # Remote and Local have the same transaction. Nothing to to here.
            i_remote += 1
            i_local += 1
        elif t_remote < t_local:
            # Remote has a transaction that Local doesn't.
            missing_transactions["missing_from_local"].append(t_remote)
            i_remote += 1  # Remote is "behind" Local.
        else:  # t_remote > t_local
            # Local has a transaction that Remote doesn't.
            missing_transactions["missing_from_remote"].append(t_local)
            i_local += 1  # Local is "behind" Remote

    # Handle remaining elements
    missing_transactions["missing_from_local"].extend(
        safe_remote_transactions[i_remote:]
    )
    missing_transactions["missing_from_remote"].extend(
        safe_local_transactions[i_local:]
    )
    return missing_transactions
