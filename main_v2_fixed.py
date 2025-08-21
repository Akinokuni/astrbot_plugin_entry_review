# -*- coding: utf-8 -*-
"""
入群申请审核插件 - 修复版本 v2
解决 NapCatQQ issue #1076: 处理入群申请时无法获取有效flag的问题

主要修复:
1. 使用多种方式获取和处理 flag
2. 增加 get_group_system_msg 轮询机制
3. 改进错误处理和重试机制
4. 增强调试功能
"""

import json
import os
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# 插件配置
CONFIG_FILE = "entry_review_config.json"
DEFAULT_CONFIG = {
    "target_groups": [],  # 需要审核的群号列表
    "review_group": 0,    # 审核群号
    "auto_approve_time": 300,  # 自动通过时间(秒)
    "debug_mode": True,   # 调试模式
    "admin_users": [],    # 管理员用户列表
    "polling_interval": 30,  # 轮询间隔(秒)
    "max_retry_count": 3,  # 最大重试次数
    "use_system_msg_polling": True  # 是否使用系统消息轮询
}

class EntryReviewPlugin:
    def __init__(self, context):
        self.context = context
        self.config = self.load_config()
        self.pending_requests = {}  # 待处理的申请
        self.processed_requests = set()  # 已处理的申请ID
        self.platform_adapter = None
        self.polling_task = None
        self.last_poll_time = datetime.now()
        
    def load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for key, value in DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    return config
            else:
                self.save_config(DEFAULT_CONFIG)
                return DEFAULT_CONFIG.copy()
        except Exception as e:
            self._debug_log(f"配置加载失败: {e}")
            return DEFAULT_CONFIG.copy()
    
    def save_config(self, config: Dict[str, Any] = None) -> bool:
        """保存配置文件"""
        try:
            config_to_save = config or self.config
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=2)
            self._debug_log("配置保存成功")
            return True
        except Exception as e:
            self._debug_log(f"配置保存失败: {e}")
            return False
    
    def _debug_log(self, message: str, level: str = "INFO"):
        """调试日志"""
        debug_mode = getattr(self, 'config', {}).get("debug_mode", True)
        if debug_mode:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] [{level}] [EntryReview] {message}")
    
    def _debug_log_event(self, event_type: str, data: Dict[str, Any]):
        """事件调试日志"""
        debug_mode = getattr(self, 'config', {}).get("debug_mode", True)
        if debug_mode:
            self._debug_log(f"事件: {event_type} | 数据: {json.dumps(data, ensure_ascii=False, indent=2)}", "EVENT")
    
    def _debug_log_api_call(self, api_name: str, params: Dict[str, Any], result: Any = None, error: str = None):
        """API调用调试日志"""
        debug_mode = getattr(self, 'config', {}).get("debug_mode", True)
        if debug_mode:
            log_data = {
                "api": api_name,
                "params": params,
                "result": result,
                "error": error
            }
            self._debug_log(f"API调用: {json.dumps(log_data, ensure_ascii=False, indent=2)}", "API")
    
    async def _get_group_system_messages(self) -> List[Dict[str, Any]]:
        """获取群系统消息"""
        try:
            result = await self.platform_adapter.get_group_system_msg()
            self._debug_log_api_call("get_group_system_msg", {}, result)
            
            if result and 'data' in result:
                return result['data']
            return []
        except Exception as e:
            self._debug_log_api_call("get_group_system_msg", {}, error=str(e))
            return []
    
    async def _try_multiple_flag_formats(self, request_data: Dict[str, Any], approve: bool, reason: str = "") -> bool:
        """尝试多种flag格式来处理申请"""
        possible_flags = []
        
        # 收集可能的flag值
        if 'flag' in request_data:
            possible_flags.append(request_data['flag'])
        if 'invitor_uin' in request_data:
            possible_flags.append(str(request_data['invitor_uin']))
        if 'user_id' in request_data:
            possible_flags.append(str(request_data['user_id']))
        if 'group_id' in request_data and 'user_id' in request_data:
            # 组合格式
            possible_flags.append(f"{request_data['group_id']}_{request_data['user_id']}")
        if 'seq' in request_data:
            possible_flags.append(str(request_data['seq']))
        
        # 尝试每种flag格式
        for flag in possible_flags:
            try:
                params = {
                    'flag': flag,
                    'approve': approve,
                    'reason': reason
                }
                
                result = await self.platform_adapter.set_group_add_request(**params)
                self._debug_log_api_call("set_group_add_request", params, result)
                
                if result and result.get('status') == 'ok':
                    self._debug_log(f"成功处理申请，使用flag: {flag}")
                    return True
                    
            except Exception as e:
                self._debug_log(f"使用flag {flag} 处理失败: {e}")
                continue
        
        self._debug_log(f"所有flag格式都失败了: {possible_flags}")
        return False
    
    async def _approve_request_v2(self, request_data: Dict[str, Any]) -> bool:
        """通过申请 - 改进版"""
        try:
            success = await self._try_multiple_flag_formats(request_data, True, "申请已通过")
            
            if success:
                # 发送通知
                group_id = request_data.get('group_id')
                user_id = request_data.get('user_id')
                if group_id and user_id:
                    await self._send_notification(
                        f"✅ 入群申请已通过\n群号: {group_id}\n用户: {user_id}"
                    )
                return True
            else:
                await self._send_notification(
                    f"❌ 处理申请失败 - 无法找到有效的flag\n数据: {json.dumps(request_data, ensure_ascii=False)}"
                )
                return False
                
        except Exception as e:
            self._debug_log(f"通过申请时发生错误: {e}")
            await self._send_notification(f"❌ 处理申请时发生错误: {e}")
            return False
    
    async def _reject_request_v2(self, request_data: Dict[str, Any], reason: str = "申请被拒绝") -> bool:
        """拒绝申请 - 改进版"""
        try:
            success = await self._try_multiple_flag_formats(request_data, False, reason)
            
            if success:
                # 发送通知
                group_id = request_data.get('group_id')
                user_id = request_data.get('user_id')
                if group_id and user_id:
                    await self._send_notification(
                        f"❌ 入群申请已拒绝\n群号: {group_id}\n用户: {user_id}\n原因: {reason}"
                    )
                return True
            else:
                await self._send_notification(
                    f"❌ 处理申请失败 - 无法找到有效的flag\n数据: {json.dumps(request_data, ensure_ascii=False)}"
                )
                return False
                
        except Exception as e:
            self._debug_log(f"拒绝申请时发生错误: {e}")
            await self._send_notification(f"❌ 处理申请时发生错误: {e}")
            return False
    
    async def _send_notification(self, message: str):
        """发送通知到审核群"""
        try:
            review_group = self.config.get('review_group')
            if review_group:
                await self.platform_adapter.send_group_msg(
                    group_id=review_group,
                    message=message
                )
        except Exception as e:
            self._debug_log(f"发送通知失败: {e}")
    
    async def _poll_system_messages(self):
        """轮询系统消息"""
        while True:
            try:
                if not self.config.get('use_system_msg_polling', True):
                    await asyncio.sleep(60)
                    continue
                
                messages = await self._get_group_system_messages()
                current_time = datetime.now()
                
                for msg in messages:
                    # 检查是否是入群申请
                    if msg.get('type') == 1 and msg.get('sub_type') == 1:
                        msg_id = f"{msg.get('group_id', '')}_{msg.get('user_id', '')}_{msg.get('seq', '')}"
                        
                        # 避免重复处理
                        if msg_id in self.processed_requests:
                            continue
                        
                        group_id = msg.get('group_id')
                        if group_id in self.config.get('target_groups', []):
                            # 处理新的入群申请
                            await self._process_system_message_request(msg)
                            self.processed_requests.add(msg_id)
                
                # 清理过期的已处理记录
                if len(self.processed_requests) > 1000:
                    self.processed_requests.clear()
                
                await asyncio.sleep(self.config.get('polling_interval', 30))
                
            except Exception as e:
                self._debug_log(f"轮询系统消息时发生错误: {e}")
                await asyncio.sleep(60)
    
    async def _process_system_message_request(self, msg: Dict[str, Any]):
        """处理系统消息中的入群申请"""
        try:
            group_id = msg.get('group_id')
            user_id = msg.get('user_id')
            comment = msg.get('comment', '')
            
            # 构建申请信息
            request_info = {
                'group_id': group_id,
                'user_id': user_id,
                'comment': comment,
                'time': datetime.now().isoformat(),
                'flag': msg.get('invitor_uin'),  # 尝试使用 invitor_uin 作为 flag
                'seq': msg.get('seq'),
                'invitor_uin': msg.get('invitor_uin'),
                'raw_data': msg
            }
            
            request_id = f"{group_id}_{user_id}_{datetime.now().timestamp()}"
            self.pending_requests[request_id] = request_info
            
            # 转发到审核群
            review_message = f"""🔔 新的入群申请
群号: {group_id}
用户: {user_id}
申请理由: {comment}
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

回复指令:
✅ 通过: /approve {request_id}
❌ 拒绝: /reject {request_id} [原因]
📋 查看: /info {request_id}"""
            
            await self._send_notification(review_message)
            
            # 启动自动通过定时器
            auto_approve_time = self.config.get('auto_approve_time', 300)
            if auto_approve_time > 0:
                asyncio.create_task(self._auto_approve_timer(request_id, auto_approve_time))
            
            self._debug_log(f"处理系统消息申请: {request_id}")
            
        except Exception as e:
            self._debug_log(f"处理系统消息申请时发生错误: {e}")
    
    async def _auto_approve_timer(self, request_id: str, delay: int):
        """自动通过定时器"""
        try:
            await asyncio.sleep(delay)
            
            if request_id in self.pending_requests:
                request_data = self.pending_requests[request_id]
                success = await self._approve_request_v2(request_data)
                
                if success:
                    del self.pending_requests[request_id]
                    await self._send_notification(f"⏰ 申请 {request_id} 已自动通过")
                
        except Exception as e:
            self._debug_log(f"自动通过定时器错误: {e}")
    
    async def handle_group_message_events(self, event):
        """处理群消息事件"""
        try:
            raw_message = event.get('raw_message', {})
            message_type = raw_message.get('message_type')
            group_id = raw_message.get('group_id')
            user_id = raw_message.get('user_id')
            message = raw_message.get('message', '')
            
            self._debug_log_event("群消息", {
                "group_id": group_id,
                "user_id": user_id,
                "message": message
            })
            
            # 只处理审核群的消息
            if group_id != self.config.get('review_group'):
                return
            
            # 检查是否是管理员
            if user_id not in self.config.get('admin_users', []):
                return
            
            # 处理审核指令
            if message.startswith('/approve '):
                request_id = message.split(' ', 1)[1].strip()
                await self._handle_approve_command(request_id)
            
            elif message.startswith('/reject '):
                parts = message.split(' ', 2)
                request_id = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else "申请被拒绝"
                await self._handle_reject_command(request_id, reason)
            
            elif message.startswith('/info '):
                request_id = message.split(' ', 1)[1].strip()
                await self._handle_info_command(request_id)
            
            elif message == '/help':
                await self._handle_help_command()
            
            elif message == '/list':
                await self._handle_list_command()
            
        except Exception as e:
            self._debug_log(f"处理群消息事件时发生错误: {e}")
    
    async def _handle_approve_command(self, request_id: str):
        """处理通过指令"""
        if request_id not in self.pending_requests:
            await self._send_notification(f"❌ 申请 {request_id} 不存在或已处理")
            return
        
        request_data = self.pending_requests[request_id]
        success = await self._approve_request_v2(request_data)
        
        if success:
            del self.pending_requests[request_id]
            await self._send_notification(f"✅ 申请 {request_id} 已通过")
        else:
            await self._send_notification(f"❌ 处理申请 {request_id} 失败")
    
    async def _handle_reject_command(self, request_id: str, reason: str):
        """处理拒绝指令"""
        if request_id not in self.pending_requests:
            await self._send_notification(f"❌ 申请 {request_id} 不存在或已处理")
            return
        
        request_data = self.pending_requests[request_id]
        success = await self._reject_request_v2(request_data, reason)
        
        if success:
            del self.pending_requests[request_id]
            await self._send_notification(f"❌ 申请 {request_id} 已拒绝，原因: {reason}")
        else:
            await self._send_notification(f"❌ 处理申请 {request_id} 失败")
    
    async def _handle_info_command(self, request_id: str):
        """处理查看信息指令"""
        if request_id not in self.pending_requests:
            await self._send_notification(f"❌ 申请 {request_id} 不存在")
            return
        
        request_data = self.pending_requests[request_id]
        info_message = f"""📋 申请信息 {request_id}
群号: {request_data.get('group_id')}
用户: {request_data.get('user_id')}
申请理由: {request_data.get('comment', '无')}
申请时间: {request_data.get('time')}
原始数据: {json.dumps(request_data.get('raw_data', {}), ensure_ascii=False, indent=2)}"""
        
        await self._send_notification(info_message)
    
    async def _handle_help_command(self):
        """处理帮助指令"""
        help_message = """📖 入群申请审核插件帮助

可用指令:
✅ /approve <申请ID> - 通过申请
❌ /reject <申请ID> [原因] - 拒绝申请
📋 /info <申请ID> - 查看申请详情
📝 /list - 查看待处理申请列表
❓ /help - 显示此帮助信息

插件会自动监听入群申请并转发到此群进行审核。"""
        
        await self._send_notification(help_message)
    
    async def _handle_list_command(self):
        """处理列表指令"""
        if not self.pending_requests:
            await self._send_notification("📝 当前没有待处理的申请")
            return
        
        list_message = "📝 待处理申请列表:\n\n"
        for request_id, request_data in self.pending_requests.items():
            list_message += f"ID: {request_id}\n"
            list_message += f"群号: {request_data.get('group_id')}\n"
            list_message += f"用户: {request_data.get('user_id')}\n"
            list_message += f"时间: {request_data.get('time')}\n\n"
        
        await self._send_notification(list_message)
    
    async def initialize(self, platform_adapter):
        """初始化插件"""
        self.platform_adapter = platform_adapter
        self._debug_log("插件初始化完成")
        
        # 启动系统消息轮询
        if self.config.get('use_system_msg_polling', True):
            self.polling_task = asyncio.create_task(self._poll_system_messages())
            self._debug_log("系统消息轮询已启动")
    
    async def cleanup(self):
        """清理资源"""
        if self.polling_task:
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        self._debug_log("插件清理完成")

# 插件实例
plugin_instance = None

def register(name, description, version, author, platform_adapter):
    """注册插件"""
    def decorator(cls):
        global plugin_instance
        plugin_instance = cls(None)
        
        async def init():
            if platform_adapter:
                await plugin_instance.initialize(platform_adapter)
        
        # 只在有事件循环时启动初始化
        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(init())
        except RuntimeError:
            # 没有运行的事件循环，跳过初始化
            pass
        
        return cls
    return decorator

@register(
    name="入群申请审核插件v2",
    description="修复版入群申请审核插件，解决flag无效问题",
    version="2.0.0",
    author="Assistant",
    platform_adapter=None
)
class RegisteredEntryReviewPlugin(EntryReviewPlugin):
    pass

# 事件处理函数
async def handle_group_message_events(event):
    """处理群消息事件"""
    if plugin_instance:
        await plugin_instance.handle_group_message_events(event)

# 清理函数
async def cleanup():
    """清理函数"""
    if plugin_instance:
        await plugin_instance.cleanup()