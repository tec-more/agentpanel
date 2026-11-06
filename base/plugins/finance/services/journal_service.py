from datetime import datetime, date
from typing import Optional, List, Dict, Any
from tortoise.transactions import atomic
from decimal import Decimal
try:
    from base.plugins.finance.models.journal import JournalEntry, JournalLine, JournalType, JournalStatus, generate_journal_no
    from base.plugins.finance.models.account import Account
    from base.plugins.finance.models.general_ledger import DailyJournal, GeneralLedger
except ImportError:
    JournalEntry = None
    JournalLine = None
    JournalType = None
    JournalStatus = None
    Account = None
    DailyJournal = None
    GeneralLedger = None


class JournalService:
    model = "journal"
    @staticmethod
    async def get_all_journals(page: int = 1, page_size: int = 20, journal_type: Optional[str] = None, 
                              status: Optional[str] = None, period: Optional[str] = None,
                              journal_date_start: Optional[str] = None, journal_date_end: Optional[str] = None,
                              keyword: Optional[str] = None) -> List[JournalEntry]:
        offset = (page - 1) * page_size
        query = JournalEntry.all().order_by("-journal_date", "-created_at")
        
        if journal_type:
            query = query.filter(journal_type=journal_type)
        
        if status:
            query = query.filter(status=status)
        
        if period:
            query = query.filter(period=period)
        
        if journal_date_start:
            query = query.filter(journal_date__gte=date.fromisoformat(journal_date_start))
        
        if journal_date_end:
            query = query.filter(journal_date__lte=date.fromisoformat(journal_date_end))
        
        if keyword:
            query = query.filter(description__icontains=keyword) | query.filter(journal_no__icontains=keyword) | query.filter(reference__icontains=keyword)
        
        return await query.offset(offset).limit(page_size)

    @staticmethod
    async def get_journal_count(journal_type: Optional[str] = None, status: Optional[str] = None, 
                                period: Optional[str] = None, journal_date_start: Optional[str] = None, 
                                journal_date_end: Optional[str] = None, keyword: Optional[str] = None) -> int:
        query = JournalEntry.all()
        
        if journal_type:
            query = query.filter(journal_type=journal_type)
        
        if status:
            query = query.filter(status=status)
        
        if period:
            query = query.filter(period=period)
        
        if journal_date_start:
            query = query.filter(journal_date__gte=date.fromisoformat(journal_date_start))
        
        if journal_date_end:
            query = query.filter(journal_date__lte=date.fromisoformat(journal_date_end))
        
        if keyword:
            query = query.filter(description__icontains=keyword) | query.filter(journal_no__icontains=keyword) | query.filter(reference__icontains=keyword)
        
        return await query.count()

    @staticmethod
    async def get_journal_by_id(journal_id: int) -> Optional[JournalEntry]:
        return await JournalEntry.get_or_none(id=journal_id)

    @staticmethod
    async def get_journal_by_no(journal_no: str) -> Optional[JournalEntry]:
        return await JournalEntry.get_or_none(journal_no=journal_no)

    @staticmethod
    @atomic()
    async def create_journal(data: Dict[str, Any]) -> JournalEntry:
        journal_date = data.get('journal_date')
        if journal_date:
            journal_date = date.fromisoformat(journal_date)
        else:
            journal_date = date.today()
        
        journal_type = JournalType(data.get('journal_type', 'general'))
        
        period = data.get('period')
        if not period:
            period = f"{journal_date.year}-{journal_date.month:02d}"
        
        lines_data = data.get('lines', [])
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")
        
        for line in lines_data:
            total_debit += Decimal(str(line.get('debit', 0)))
            total_credit += Decimal(str(line.get('credit', 0)))
        
        if total_debit != total_credit:
            raise ValueError("借贷不平衡")
        
        journal = await JournalEntry.create(
            journal_no=generate_journal_no(),
            journal_date=journal_date,
            journal_type=journal_type,
            status=JournalStatus.DRAFT,
            period=period,
            reference=data.get('reference'),
            description=data.get('description'),
            total_debit=total_debit,
            total_credit=total_credit,
            created_by=data.get('created_by'),
            remark=data.get('remark')
        )
        
        for idx, line_data in enumerate(lines_data):
            account = await Account.get_or_none(id=line_data['account_id'])
            if not account:
                raise ValueError(f"会计科目ID {line_data['account_id']} 不存在")
            
            await JournalLine.create(
                journal_entry=journal,
                sequence=line_data.get('sequence', idx + 1),
                account=account,
                description=line_data.get('description'),
                debit=Decimal(str(line_data.get('debit', 0))),
                credit=Decimal(str(line_data.get('credit', 0))),
                tax_amount=Decimal(str(line_data.get('tax_amount', 0))),
                tax_code=line_data.get('tax_code'),
                currency_code=line_data.get('currency_code', 'CNY'),
                exchange_rate=Decimal(str(line_data.get('exchange_rate', 1))),
                original_amount=Decimal(str(line_data.get('original_amount', 0))),
                partner_id=line_data.get('partner_id'),
                partner_type=line_data.get('partner_type'),
                analytic_account_id=line_data.get('analytic_account_id'),
                remark=line_data.get('remark')
            )
        
        return journal

    @staticmethod
    @atomic()
    async def update_journal(journal_id: int, data: Dict[str, Any]) -> Optional[JournalEntry]:
        journal = await JournalEntry.get_or_none(id=journal_id)
        if not journal:
            return None
        
        if journal.status == JournalStatus.POSTED:
            raise ValueError("已过账的凭证不能修改")
        
        update_data = {}
        
        if 'journal_date' in data:
            update_data['journal_date'] = date.fromisoformat(data['journal_date'])
            if 'period' not in data:
                jd = update_data['journal_date']
                update_data['period'] = f"{jd.year}-{jd.month:02d}"
        
        if 'journal_type' in data:
            update_data['journal_type'] = JournalType(data['journal_type'])
        
        if 'period' in data:
            update_data['period'] = data['period']
        
        if 'reference' in data:
            update_data['reference'] = data['reference']
        
        if 'description' in data:
            update_data['description'] = data['description']
        
        if 'remark' in data:
            update_data['remark'] = data['remark']
        
        if update_data:
            await JournalEntry.filter(id=journal_id).update(**update_data)
        
        return await JournalEntry.get(id=journal_id)

    @staticmethod
    @atomic()
    async def confirm_journal(journal_id: int, confirmed_by: Optional[str] = None) -> bool:
        journal = await JournalEntry.get_or_none(id=journal_id)
        if not journal:
            return False
        
        if journal.status != JournalStatus.DRAFT:
            raise ValueError("只能审核草稿状态的凭证")
        
        if not journal.is_balanced:
            raise ValueError("凭证借贷不平衡，无法审核")
        
        await JournalEntry.filter(id=journal_id).update(
            status=JournalStatus.CONFIRMED,
            confirmed_by=confirmed_by,
            confirmed_at=datetime.now()
        )
        return True

    @staticmethod
    @atomic()
    async def post_journal(journal_id: int, posted_by: Optional[str] = None) -> bool:
        journal = await JournalEntry.get_or_none(id=journal_id)
        if not journal:
            return False
        
        if journal.status != JournalStatus.CONFIRMED:
            raise ValueError("只能过账已审核的凭证")
        
        await JournalEntry.filter(id=journal_id).update(
            status=JournalStatus.POSTED,
            posted_by=posted_by,
            posted_at=datetime.now()
        )
        
        await JournalService._update_account_balances(journal)
        await JournalService._create_daily_journal(journal)
        
        return True

    @staticmethod
    @atomic()
    async def cancel_journal(journal_id: int, cancelled_by: Optional[str] = None) -> bool:
        journal = await JournalEntry.get_or_none(id=journal_id)
        if not journal:
            return False
        
        if journal.status == JournalStatus.CANCELLED:
            return True
        
        if journal.status == JournalStatus.POSTED:
            await JournalService._reverse_account_balances(journal)
        
        await JournalEntry.filter(id=journal_id).update(
            status=JournalStatus.CANCELLED,
            cancelled_by=cancelled_by,
            cancelled_at=datetime.now()
        )
        return True

    @staticmethod
    @atomic()
    async def _update_account_balances(journal: JournalEntry) -> None:
        lines = await journal.lines.all().prefetch_related('account')
        
        for line in lines:
            if line.debit > 0:
                await Account.filter(id=line.account.id).update(
                    debit_balance=Account.debit_balance + line.debit
                )
            
            if line.credit > 0:
                await Account.filter(id=line.account.id).update(
                    credit_balance=Account.credit_balance + line.credit
                )

    @staticmethod
    @atomic()
    async def _reverse_account_balances(journal: JournalEntry) -> None:
        lines = await journal.lines.all().prefetch_related('account')
        
        for line in lines:
            if line.debit > 0:
                await Account.filter(id=line.account.id).update(
                    debit_balance=Account.debit_balance - line.debit
                )
            
            if line.credit > 0:
                await Account.filter(id=line.account.id).update(
                    credit_balance=Account.credit_balance - line.credit
                )

    @staticmethod
    @atomic()
    async def _create_daily_journal(journal: JournalEntry) -> None:
        lines = await journal.lines.all().prefetch_related('account')
        
        for line in lines:
            account_balance = await Account.get_or_none(id=line.account.id)
            if account_balance:
                balance = float(account_balance.debit_balance) - float(account_balance.credit_balance)
                balance_type = "debit" if balance >= 0 else "credit"
                
                await DailyJournal.create(
                    journal_date=journal.journal_date,
                    period=journal.period,
                    account=line.account,
                    description=line.description or journal.description,
                    reference=journal.journal_no,
                    debit=line.debit,
                    credit=line.credit,
                    balance=abs(balance),
                    balance_type=balance_type,
                    journal_entry_id=journal.id
                )

    @staticmethod
    async def get_journal_types() -> List[Dict[str, str]]:
        return [
            {"value": JournalType.GENERAL.value, "label": JournalType.GENERAL.get_label(JournalType.GENERAL.value)},
            {"value": JournalType.PURCHASE.value, "label": JournalType.PURCHASE.get_label(JournalType.PURCHASE.value)},
            {"value": JournalType.SALE.value, "label": JournalType.SALE.get_label(JournalType.SALE.value)},
            {"value": JournalType.PAYMENT.value, "label": JournalType.PAYMENT.get_label(JournalType.PAYMENT.value)},
            {"value": JournalType.RECEIPT.value, "label": JournalType.RECEIPT.get_label(JournalType.RECEIPT.value)},
            {"value": JournalType.INVENTORY.value, "label": JournalType.INVENTORY.get_label(JournalType.INVENTORY.value)},
        ]

    @staticmethod
    async def get_journal_statuses() -> List[Dict[str, str]]:
        return [
            {"value": JournalStatus.DRAFT.value, "label": JournalStatus.DRAFT.get_label(JournalStatus.DRAFT.value), "color": JournalStatus.DRAFT.get_color(JournalStatus.DRAFT.value)},
            {"value": JournalStatus.CONFIRMED.value, "label": JournalStatus.CONFIRMED.get_label(JournalStatus.CONFIRMED.value), "color": JournalStatus.CONFIRMED.get_color(JournalStatus.CONFIRMED.value)},
            {"value": JournalStatus.POSTED.value, "label": JournalStatus.POSTED.get_label(JournalStatus.POSTED.value), "color": JournalStatus.POSTED.get_color(JournalStatus.POSTED.value)},
            {"value": JournalStatus.CANCELLED.value, "label": JournalStatus.CANCELLED.get_label(JournalStatus.CANCELLED.value), "color": JournalStatus.CANCELLED.get_color(JournalStatus.CANCELLED.value)},
        ]