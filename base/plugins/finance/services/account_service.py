from datetime import datetime
from typing import Optional, List, Dict, Any
from tortoise.transactions import atomic
from decimal import Decimal
try:
    from base.plugins.finance.models.account import Account, AccountType
except ImportError:
    Account = None
    AccountType = None


class AccountService:
    model = "account"
    @staticmethod
    async def get_all_accounts(page: int = 1, page_size: int = 20, account_type: Optional[str] = None, keyword: Optional[str] = None) -> List[Account]:
        offset = (page - 1) * page_size
        query = Account.all().order_by("code")
        
        if account_type:
            query = query.filter(account_type=account_type)
        
        if keyword:
            query = query.filter(name__icontains=keyword) | query.filter(code__icontains=keyword)
        
        return await query.offset(offset).limit(page_size)

    @staticmethod
    async def get_account_count(account_type: Optional[str] = None, keyword: Optional[str] = None) -> int:
        query = Account.all()
        
        if account_type:
            query = query.filter(account_type=account_type)
        
        if keyword:
            query = query.filter(name__icontains=keyword) | query.filter(code__icontains=keyword)
        
        return await query.count()

    @staticmethod
    async def get_account_by_id(account_id: int) -> Optional[Account]:
        return await Account.get_or_none(id=account_id)

    @staticmethod
    async def get_account_by_code(code: str) -> Optional[Account]:
        return await Account.get_or_none(code=code)

    @staticmethod
    @atomic()
    async def create_account(data: Dict[str, Any]) -> Account:
        parent_id = data.get('parent_id')
        level = 1
        
        if parent_id:
            parent = await Account.get_or_none(id=parent_id)
            if parent:
                level = parent.level + 1
                await Account.filter(id=parent_id).update(is_leaf=False)
            else:
                parent_id = None
        
        account = await Account.create(
            code=data['code'],
            name=data['name'],
            account_type=AccountType(data['account_type']),
            parent_id=parent_id,
            level=level,
            description=data.get('description'),
            tax_code=data.get('tax_code'),
            currency_code=data.get('currency_code', 'CNY'),
            reconcile=data.get('reconcile', False),
            active=data.get('active', True)
        )
        
        return account

    @staticmethod
    @atomic()
    async def update_account(account_id: int, data: Dict[str, Any]) -> Optional[Account]:
        account = await Account.get_or_none(id=account_id)
        if not account:
            return None
        
        update_data = {}
        
        if 'name' in data:
            update_data['name'] = data['name']
        if 'account_type' in data:
            update_data['account_type'] = AccountType(data['account_type'])
        if 'parent_id' in data:
            if account.parent_id != data['parent_id']:
                if account.parent_id:
                    old_parent = await Account.get_or_none(id=account.parent_id)
                    if old_parent:
                        child_count = await Account.filter(parent_id=old_parent.id).count()
                        if child_count <= 1:
                            await Account.filter(id=old_parent.id).update(is_leaf=True)
                
                new_parent_id = data['parent_id']
                if new_parent_id:
                    new_parent = await Account.get_or_none(id=new_parent_id)
                    if new_parent:
                        update_data['level'] = new_parent.level + 1
                        await Account.filter(id=new_parent_id).update(is_leaf=False)
                    else:
                        new_parent_id = None
                        update_data['level'] = 1
                else:
                    update_data['level'] = 1
                
                update_data['parent_id'] = new_parent_id
        
        if 'description' in data:
            update_data['description'] = data['description']
        if 'tax_code' in data:
            update_data['tax_code'] = data['tax_code']
        if 'currency_code' in data:
            update_data['currency_code'] = data['currency_code']
        if 'reconcile' in data:
            update_data['reconcile'] = data['reconcile']
        if 'active' in data:
            update_data['active'] = data['active']
        
        await Account.filter(id=account_id).update(**update_data)
        return await Account.get(id=account_id)

    @staticmethod
    @atomic()
    async def delete_account(account_id: int) -> bool:
        account = await Account.get_or_none(id=account_id)
        if not account:
            return False
        
        children = await Account.filter(parent_id=account_id).count()
        if children > 0:
            raise ValueError("该科目有子科目，无法删除")
        
        if account.parent_id:
            parent = await Account.get_or_none(id=account.parent_id)
            if parent:
                child_count = await Account.filter(parent_id=parent.id).count()
                if child_count <= 1:
                    await Account.filter(id=parent.id).update(is_leaf=True)
        
        await account.delete()
        return True

    @staticmethod
    async def get_account_tree() -> List[Dict[str, Any]]:
        accounts = await Account.all().order_by("code")
        account_map = {acc.id: await acc.to_dict() for acc in accounts}
        
        tree = []
        for acc_dict in account_map.values():
            if acc_dict['parent_id'] is None:
                tree.append(acc_dict)
            else:
                parent_dict = account_map.get(acc_dict['parent_id'])
                if parent_dict and 'children' not in parent_dict:
                    parent_dict['children'] = []
                if parent_dict:
                    parent_dict['children'].append(acc_dict)
        
        return tree

    @staticmethod
    async def get_account_types() -> List[Dict[str, str]]:
        return [
            {"value": AccountType.ASSET.value, "label": AccountType.ASSET.get_label(AccountType.ASSET.value), "color": AccountType.ASSET.get_color(AccountType.ASSET.value)},
            {"value": AccountType.LIABILITY.value, "label": AccountType.LIABILITY.get_label(AccountType.LIABILITY.value), "color": AccountType.LIABILITY.get_color(AccountType.LIABILITY.value)},
            {"value": AccountType.EQUITY.value, "label": AccountType.EQUITY.get_label(AccountType.EQUITY.value), "color": AccountType.EQUITY.get_color(AccountType.EQUITY.value)},
            {"value": AccountType.INCOME.value, "label": AccountType.INCOME.get_label(AccountType.INCOME.value), "color": AccountType.INCOME.get_color(AccountType.INCOME.value)},
            {"value": AccountType.EXPENSE.value, "label": AccountType.EXPENSE.get_label(AccountType.EXPENSE.value), "color": AccountType.EXPENSE.get_color(AccountType.EXPENSE.value)},
        ]

    @staticmethod
    @atomic()
    async def initialize_default_accounts() -> None:
        default_accounts = [
            {"code": "1001", "name": "库存现金", "account_type": "asset", "parent_code": None},
            {"code": "1002", "name": "银行存款", "account_type": "asset", "parent_code": None},
            {"code": "1121", "name": "应收票据", "account_type": "asset", "parent_code": None},
            {"code": "1122", "name": "应收账款", "account_type": "asset", "parent_code": None},
            {"code": "1123", "name": "预付账款", "account_type": "asset", "parent_code": None},
            {"code": "1403", "name": "原材料", "account_type": "asset", "parent_code": None},
            {"code": "1405", "name": "库存商品", "account_type": "asset", "parent_code": None},
            {"code": "1601", "name": "固定资产", "account_type": "asset", "parent_code": None},
            {"code": "2001", "name": "短期借款", "account_type": "liability", "parent_code": None},
            {"code": "2201", "name": "应付票据", "account_type": "liability", "parent_code": None},
            {"code": "2202", "name": "应付账款", "account_type": "liability", "parent_code": None},
            {"code": "2203", "name": "预收账款", "account_type": "liability", "parent_code": None},
            {"code": "2211", "name": "应付职工薪酬", "account_type": "liability", "parent_code": None},
            {"code": "2221", "name": "应交税费", "account_type": "liability", "parent_code": None},
            {"code": "4001", "name": "实收资本", "account_type": "equity", "parent_code": None},
            {"code": "4002", "name": "资本公积", "account_type": "equity", "parent_code": None},
            {"code": "4103", "name": "本年利润", "account_type": "equity", "parent_code": None},
            {"code": "4104", "name": "利润分配", "account_type": "equity", "parent_code": None},
            {"code": "5001", "name": "生产成本", "account_type": "expense", "parent_code": None},
            {"code": "5101", "name": "制造费用", "account_type": "expense", "parent_code": None},
            {"code": "6001", "name": "主营业务收入", "account_type": "income", "parent_code": None},
            {"code": "6051", "name": "其他业务收入", "account_type": "income", "parent_code": None},
            {"code": "6301", "name": "营业外收入", "account_type": "income", "parent_code": None},
            {"code": "6401", "name": "主营业务成本", "account_type": "expense", "parent_code": None},
            {"code": "6402", "name": "其他业务成本", "account_type": "expense", "parent_code": None},
            {"code": "6601", "name": "销售费用", "account_type": "expense", "parent_code": None},
            {"code": "6602", "name": "管理费用", "account_type": "expense", "parent_code": None},
            {"code": "6603", "name": "财务费用", "account_type": "expense", "parent_code": None},
            {"code": "6711", "name": "营业外支出", "account_type": "expense", "parent_code": None},
        ]
        
        code_map = {}
        for acc_data in default_accounts:
            existing = await Account.get_or_none(code=acc_data['code'])
            if existing:
                code_map[acc_data['code']] = existing.id
                continue
            
            parent_id = None
            level = 1
            if acc_data['parent_code']:
                parent_id = code_map.get(acc_data['parent_code'])
                if parent_id:
                    parent = await Account.get_or_none(id=parent_id)
                    if parent:
                        level = parent.level + 1
                        await Account.filter(id=parent_id).update(is_leaf=False)
            
            account = await Account.create(
                code=acc_data['code'],
                name=acc_data['name'],
                account_type=AccountType(acc_data['account_type']),
                parent_id=parent_id,
                level=level,
                is_leaf=True
            )
            code_map[acc_data['code']] = account.id