import asyncio
import time
import re
from typing import Dict, Any, Optional
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import json
import os

@register("astrbot_plugin_entry_review_fixed", "Developer", "入群申请审核插件（修复版），自动转发入群申请到指定群聊进行审核", "1.1.0")
class EntryReviewPluginFixed(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.pending_requests: Dict[str, Dict[str, Any]] = {}
        self.config = {}
        self.debug_mode = False
        self.debug_log_events = True
        self.debug_log_api_calls = True
    
    async def initialize(self):
        """初始化插件"""
        self.load_config()
        self._init_debug_mode()
        
        # 注册事件监听器 - 使用正确的事件类型
        try:
            # 尝试注册请求事件监听器
            platform_adapter = self.context.get_platform_adapter()
            if platform_adapter and hasattr(platform_adapter, 'register_event_handler'):
                await platform_adapter.register_event_handler('request', self._handle_request_event)
                self._debug_log("已注册请求事件监听器", "INFO")
            else:
                self._debug_log("平台适配器不支持事件监听器注册，将使用消息监听方式", "WARNING")
        except Exception as e:
            self._debug_log(f"注册事件监听器失败: {e}", "ERROR")
        
        logger.info("入群申请审核插件（修复版）已初始化")
    
    def load_config(self):
        """加载配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                # 默认配置
                self.config = {
                    "source_group_id": "",
                    "target_group_id": "", 
                    "reviewers": [],
                    "enable_auto_approve": True,
                    "auto_approve_timeout": 3600,
                    "approval_message_template": "欢迎 {nickname} 加入群聊！",
                    "rejection_message_template": "很抱歉，您的入群申请未通过审核。原因：{reason}",
                    "debug_mode": True,
                    "debug_log_events": True,
                    "debug_log_api_calls": True
                }
                self.save_config()
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            self.config = {
                "source_group_id": "",
                "target_group_id": "", 
                "reviewers": [],
                "enable_auto_approve": True,
                "auto_approve_timeout": 3600,
                "debug_mode": True,
                "debug_log_events": True,
                "debug_log_api_calls": True
            }
    
    def _init_debug_mode(self):
        """初始化调试模式"""
        self.debug_mode = self.config.get("debug_mode", True)
        self.debug_log_events = self.config.get("debug_log_events", True)
        self.debug_log_api_calls = self.config.get("debug_log_api_calls", True)
        
        if self.debug_mode:
            logger.info("🐛 调试模式已启用")
            logger.info(f"📝 事件详情记录: {'启用' if self.debug_log_events else '禁用'}")
            logger.info(f"🔗 API调用记录: {'启用' if self.debug_log_api_calls else '禁用'}")
    
    def _debug_log(self, message: str, level: str = "DEBUG"):
        """输出调试日志"""
        if getattr(self, 'debug_mode', False):
            if level == "INFO":
                logger.info(f"🐛 [DEBUG] {message}")
            elif level == "WARNING":
                logger.warning(f"🐛 [DEBUG] {message}")
            elif level == "ERROR":
                logger.error(f"🐛 [DEBUG] {message}")
            else:
                logger.debug(f"🐛 [DEBUG] {message}")
    
    def _debug_log_event(self, event_data: dict, action: str):
        """记录事件详情"""
        if getattr(self, 'debug_mode', False) and getattr(self, 'debug_log_events', False):
            self._debug_log(f"事件处理 - {action}")
            self._debug_log(f"  事件数据: {str(event_data)[:200]}...")
    
    def _debug_log_api_call(self, api_name: str, params: dict, result: Any = None, error: Exception = None):
        """记录API调用详情"""
        if getattr(self, 'debug_mode', False) and getattr(self, 'debug_log_api_calls', False):
            self._debug_log(f"API调用 - {api_name}")
            self._debug_log(f"  参数: {params}")
            if result is not None:
                self._debug_log(f"  结果: {str(result)[:200]}...")
            if error:
                self._debug_log(f"  错误: {str(error)}", "ERROR")

    def save_config(self):
        """保存配置"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
    
    async def _handle_request_event(self, event_data: dict):
        """处理请求事件（新的事件处理方式）"""
        try:
            self._debug_log_event(event_data, "处理请求事件")
            
            # 检查是否是群组加入请求
            if (event_data.get('post_type') == 'request' and 
                event_data.get('request_type') == 'group' and
                event_data.get('sub_type') == 'add'):
                
                await self._process_group_request_new(event_data)
                
        except Exception as e:
            logger.error(f"处理请求事件失败: {e}")
            self._debug_log(f"处理请求事件失败: {e}", "ERROR")
    
    async def _process_group_request_new(self, event_data: dict):
        """处理入群申请（新版本）"""
        try:
            user_id = str(event_data.get('user_id', ''))
            group_id = str(event_data.get('group_id', ''))
            comment = event_data.get('comment', '无')
            flag = event_data.get('flag', '')
            
            self._debug_log(f"入群申请详情 - 用户ID: {user_id}, 群ID: {group_id}, 申请理由: {comment}, Flag: {flag}")
            
            # 检查是否是配置的源群
            if group_id != self.config.get("source_group_id"):
                self._debug_log(f"群ID不匹配，忽略申请 - 当前群: {group_id}, 配置源群: {self.config.get('source_group_id')}")
                return
            
            # 获取申请者信息
            nickname = f"用户{user_id}"
            
            # 尝试获取用户昵称
            try:
                platform_adapter = self.context.get_platform_adapter()
                if platform_adapter and hasattr(platform_adapter, 'get_stranger_info'):
                    user_info = await platform_adapter.get_stranger_info(user_id=int(user_id))
                    if user_info and 'nickname' in user_info:
                        nickname = user_info['nickname']
                        self._debug_log(f"获取到用户昵称: {nickname}")
            except Exception as e:
                self._debug_log(f"获取用户信息失败: {e}", "WARNING")
            
            # 存储申请信息
            request_info = {
                'user_id': user_id,
                'group_id': group_id,
                'nickname': nickname,
                'comment': comment,
                'flag': flag,
                'timestamp': int(time.time()),
                'status': 'pending',
                'event_data': event_data  # 保存完整的事件数据
            }
            
            self.pending_requests[user_id] = request_info
            
            # 转发到审核群
            target_group_id = self.config.get("target_group_id")
            if target_group_id:
                review_message = f"""📝 新的入群申请
👤 申请人：{nickname} ({user_id})
🏠 申请群：{group_id}
💬 申请理由：{comment}
🏷️ Flag：{flag}
⏰ 申请时间：{self._format_timestamp()}

请审核员回复：
✅ /通过 {user_id}
❌ /拒绝 {user_id} [原因]"""
                
                await self.send_message_to_group(target_group_id, review_message)
                
                # 设置自动通过定时器
                if self.config.get("enable_auto_approve", True):
                    timeout = self.config.get("auto_approve_timeout", 3600)
                    asyncio.create_task(self._auto_approve_after_timeout(user_id, int(group_id), nickname, flag))
                    
            logger.info(f"处理入群申请：用户 {user_id} 申请加入群 {group_id}")
            
        except Exception as e:
            logger.error(f"处理入群申请失败: {e}")
            self._debug_log(f"处理入群申请失败: {e}", "ERROR")
    
    @filter.command("设置源群")
    async def set_source_group(self, event: AstrMessageEvent, group_id: str):
        """设置源群ID"""
        try:
            self.config["source_group_id"] = group_id
            self.save_config()
            event.set_result(MessageEventResult().message(f"✅ 已设置源群ID为：{group_id}"))
            logger.info(f"设置源群ID：{group_id}")
        except Exception as e:
            logger.error(f"设置源群ID失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 设置失败：{str(e)}"))
    
    @filter.command("设置审核群")
    async def set_target_group(self, event: AstrMessageEvent, group_id: str):
        """设置审核群ID"""
        try:
            self.config["target_group_id"] = group_id
            self.save_config()
            event.set_result(MessageEventResult().message(f"✅ 已设置审核群ID为：{group_id}"))
            logger.info(f"设置审核群ID：{group_id}")
        except Exception as e:
            logger.error(f"设置审核群ID失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 设置失败：{str(e)}"))
    
    @filter.command("添加审核员")
    async def add_reviewer(self, event: AstrMessageEvent, user_id: str):
        """添加审核员"""
        try:
            if "reviewers" not in self.config:
                self.config["reviewers"] = []
            if user_id not in self.config["reviewers"]:
                self.config["reviewers"].append(user_id)
                self.save_config()
                event.set_result(MessageEventResult().message(f"✅ 已添加审核员：{user_id}"))
                logger.info(f"添加审核员：{user_id}")
            else:
                event.set_result(MessageEventResult().message(f"ℹ️ 用户 {user_id} 已经是审核员了"))
        except Exception as e:
            logger.error(f"添加审核员失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 添加失败：{str(e)}"))
    
    @filter.command("查看配置")
    async def show_config(self, event: AstrMessageEvent):
        """查看当前配置"""
        config_text = f"""📋 当前配置：
🏠 源群ID：{self.config.get('source_group_id', '未设置')}
🎯 审核群ID：{self.config.get('target_group_id', '未设置')}
👥 审核员：{', '.join(self.config.get('reviewers', []))}
⏰ 自动通过：{'启用' if self.config.get('enable_auto_approve', True) else '禁用'}
🕐 超时时间：{self.config.get('auto_approve_timeout', 3600)}秒
🐛 调试模式：{'启用' if self.config.get('debug_mode', False) else '禁用'}"""
        event.set_result(MessageEventResult().message(config_text))
    
    def _safe_format(self, template: str, **kwargs) -> str:
        """安全格式化字符串"""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.warning(f"格式化模板缺少参数: {e}")
            return template
    
    def _format_timestamp(self, timestamp: Optional[int] = None) -> str:
        """格式化时间戳"""
        if timestamp is None:
            timestamp = int(time.time())
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
    
    # 保持原有的消息监听作为备用方案
    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_group_request_events(self, event: AstrMessageEvent, *args, **kwargs):
        """处理群组相关事件，包括入群申请（备用方案）"""
        try:
            # 检查是否是入群申请事件
            raw_message = getattr(event, 'raw_message', None)
            if raw_message and hasattr(raw_message, 'post_type'):
                if raw_message.post_type == 'request' and raw_message.request_type == 'group':
                    # 转换为新的事件数据格式
                    event_data = {
                        'post_type': 'request',
                        'request_type': 'group',
                        'sub_type': 'add',
                        'user_id': getattr(raw_message, 'user_id', ''),
                        'group_id': getattr(raw_message, 'group_id', ''),
                        'comment': getattr(raw_message, 'comment', '无'),
                        'flag': getattr(raw_message, 'flag', '')
                    }
                    await self._process_group_request_new(event_data)
                    return
            
            # 检查是否是审核群的审核指令
            if event.get_group_id() == self.config.get("target_group_id"):
                context = kwargs.get('context')
                await self._process_review_command(event, context)
        except Exception as e:
            logger.error(f"处理群组事件失败: {e}")
    
    async def send_message_to_group(self, group_id: str, message: str):
        """发送消息到群组"""
        try:
            self._debug_log_api_call("send_message_to_group", {"group_id": group_id, "message": message[:50] + "..."})
            
            platform_adapter = self.context.get_platform_adapter()
            if platform_adapter and hasattr(platform_adapter, 'send_group_msg'):
                result = await platform_adapter.send_group_msg(
                    group_id=int(group_id),
                    message=message
                )
                self._debug_log_api_call("send_message_to_group", {"group_id": group_id}, result)
                return result
            else:
                logger.warning("平台适配器不支持发送群消息")
                return None
        except Exception as e:
            logger.error(f"发送群消息失败: {e}")
            self._debug_log_api_call("send_message_to_group", {"group_id": group_id}, error=e)
            return None
    
    @filter.command("测试申请")
    async def test_group_request(self, event: AstrMessageEvent, user_id: str = "123456789", group_id: str = "987654321", comment: str = "测试申请"):
        """测试入群申请功能"""
        try:
            # 模拟入群申请事件数据
            test_event_data = {
                'post_type': 'request',
                'request_type': 'group',
                'sub_type': 'add',
                'user_id': user_id,
                'group_id': self.config.get("source_group_id", group_id),
                'comment': comment,
                'flag': f"test_flag_{int(time.time())}",
                'time': int(time.time())
            }
            
            await self._process_group_request_new(test_event_data)
            event.set_result(MessageEventResult().message(f"✅ 已模拟用户 {user_id} 的入群申请"))
            
        except Exception as e:
            logger.error(f"测试入群申请失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 测试失败：{str(e)}"))
    
    async def _process_review_command(self, event: AstrMessageEvent, context=None):
        """处理审核指令"""
        try:
            message = event.message_str.strip()
            
            # 通过申请
            approve_match = re.match(r'^/通过\s+(\d+)', message)
            if approve_match:
                user_id = approve_match.group(1)
                operator = str(event.sender_id)
                await self._approve_request(event, user_id, operator, context)
                return
            
            # 拒绝申请
            reject_match = re.match(r'^/拒绝\s+(\d+)(?:\s+(.+))?', message)
            if reject_match:
                user_id = reject_match.group(1)
                reason = reject_match.group(2) or "未通过审核"
                operator = str(event.sender_id)
                await self._reject_request(event, user_id, operator, reason, context)
                return
                
        except Exception as e:
            logger.error(f"处理审核指令失败: {e}")
    
    async def _approve_request(self, event: AstrMessageEvent, user_id: str, operator: str, context=None):
        """通过入群申请（修复版）"""
        try:
            self._debug_log(f"通过申请 - 用户ID: {user_id}, 操作员: {operator}")
            
            if user_id not in self.pending_requests:
                self._debug_log(f"未找到申请记录 - 用户ID: {user_id}", "WARNING")
                event.set_result(MessageEventResult().message(f"❌ 未找到用户 {user_id} 的申请记录"))
                return
            
            request_info = self.pending_requests[user_id]
            if request_info['status'] != 'pending':
                event.set_result(MessageEventResult().message(f"❌ 用户 {user_id} 的申请已经被处理过了"))
                return
            
            # 更新申请状态
            request_info['status'] = 'approved'
            request_info['operator'] = operator
            request_info['process_time'] = int(time.time())
            
            # 调用平台API通过申请（修复版）
            success = await self._call_set_group_add_request(request_info, True)
            
            if success:
                # 发送通知消息
                approval_message = self._safe_format(
                    self.config.get("approval_message_template", "欢迎 {nickname} 加入群聊！"),
                    nickname=request_info['nickname'],
                    user_id=user_id
                )
                
                # 发送到源群
                source_group_id = self.config.get("source_group_id")
                if source_group_id:
                    await self.send_message_to_group(source_group_id, approval_message)
                
                # 回复审核结果
                result_message = f"✅ 已通过用户 {request_info['nickname']} ({user_id}) 的入群申请"
                event.set_result(MessageEventResult().message(result_message))
                
                logger.info(f"通过入群申请：用户 {user_id}，操作员 {operator}")
            else:
                event.set_result(MessageEventResult().message(f"⚠️ 申请已记录为通过，但API调用可能失败"))
            
            # 清理申请记录
            await self._cleanup_request(user_id)
            
        except Exception as e:
            logger.error(f"通过入群申请失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 处理申请失败：{str(e)}"))
    
    async def _reject_request(self, event: AstrMessageEvent, user_id: str, operator: str, reason: str = "", context=None):
        """拒绝入群申请（修复版）"""
        try:
            self._debug_log(f"拒绝申请 - 用户ID: {user_id}, 操作员: {operator}, 原因: {reason}")
            
            if user_id not in self.pending_requests:
                self._debug_log(f"未找到申请记录 - 用户ID: {user_id}", "WARNING")
                event.set_result(MessageEventResult().message(f"❌ 未找到用户 {user_id} 的申请记录"))
                return
            
            request_info = self.pending_requests[user_id]
            if request_info['status'] != 'pending':
                event.set_result(MessageEventResult().message(f"❌ 用户 {user_id} 的申请已经被处理过了"))
                return
            
            # 更新申请状态
            request_info['status'] = 'rejected'
            request_info['operator'] = operator
            request_info['process_time'] = int(time.time())
            request_info['reject_reason'] = reason
            
            # 调用平台API拒绝申请（修复版）
            success = await self._call_set_group_add_request(request_info, False, reason)
            
            if success:
                # 回复审核结果
                result_message = f"❌ 已拒绝用户 {request_info['nickname']} ({user_id}) 的入群申请\n原因：{reason or '未通过审核'}"
                event.set_result(MessageEventResult().message(result_message))
                
                logger.info(f"拒绝入群申请：用户 {user_id}，操作员 {operator}，原因 {reason}")
            else:
                event.set_result(MessageEventResult().message(f"⚠️ 申请已记录为拒绝，但API调用可能失败"))
            
            # 清理申请记录
            await self._cleanup_request(user_id)
            
        except Exception as e:
            logger.error(f"拒绝入群申请失败: {e}")
            event.set_result(MessageEventResult().message(f"❌ 处理申请失败：{str(e)}"))
    
    async def _call_set_group_add_request(self, request_info: dict, approve: bool, reason: str = "") -> bool:
        """调用set_group_add_request API（修复版）"""
        try:
            platform_adapter = self.context.get_platform_adapter()
            if not platform_adapter:
                self._debug_log("平台适配器不可用", "ERROR")
                return False
            
            flag = request_info.get('flag', '')
            if not flag:
                self._debug_log("Flag为空，尝试使用替代方案", "WARNING")
                # 尝试从事件数据中获取flag
                event_data = request_info.get('event_data', {})
                flag = event_data.get('flag', '')
            
            # 准备API调用参数
            api_params = {
                'flag': flag,
                'sub_type': 'add',
                'approve': approve
            }
            
            if not approve and reason:
                api_params['reason'] = reason
            
            self._debug_log_api_call("set_group_add_request", api_params)
            
            # 尝试多种API调用方式
            success = False
            
            # 方式1：标准API调用
            if hasattr(platform_adapter, 'set_group_add_request'):
                try:
                    result = await platform_adapter.set_group_add_request(**api_params)
                    self._debug_log_api_call("set_group_add_request", api_params, result)
                    success = True
                except Exception as e:
                    self._debug_log_api_call("set_group_add_request", api_params, error=e)
                    self._debug_log(f"标准API调用失败: {e}", "WARNING")
            
            # 方式2：如果标准方式失败，尝试直接调用底层API
            if not success and hasattr(platform_adapter, 'call_api'):
                try:
                    result = await platform_adapter.call_api('set_group_add_request', api_params)
                    self._debug_log_api_call("call_api(set_group_add_request)", api_params, result)
                    success = True
                except Exception as e:
                    self._debug_log_api_call("call_api(set_group_add_request)", api_params, error=e)
                    self._debug_log(f"底层API调用失败: {e}", "WARNING")
            
            # 方式3：如果都失败，尝试使用用户ID和群ID的组合方式
            if not success:
                try:
                    alternative_params = {
                        'user_id': int(request_info['user_id']),
                        'group_id': int(request_info['group_id']),
                        'approve': approve
                    }
                    if not approve and reason:
                        alternative_params['reason'] = reason
                    
                    if hasattr(platform_adapter, 'set_group_add_request'):
                        result = await platform_adapter.set_group_add_request(**alternative_params)
                        self._debug_log_api_call("set_group_add_request(alternative)", alternative_params, result)
                        success = True
                except Exception as e:
                    self._debug_log_api_call("set_group_add_request(alternative)", alternative_params, error=e)
                    self._debug_log(f"替代方案API调用失败: {e}", "ERROR")
            
            if not success:
                self._debug_log("所有API调用方式都失败了", "ERROR")
            
            return success
            
        except Exception as e:
            logger.error(f"调用set_group_add_request API失败: {e}")
            self._debug_log(f"调用set_group_add_request API失败: {e}", "ERROR")
            return False
    
    async def _auto_approve_after_timeout(self, user_id: str, group_id: int, nickname: str, flag: str):
        """超时自动通过"""
        try:
            timeout = self.config.get("auto_approve_timeout", 3600)
            await asyncio.sleep(timeout)
            
            # 检查申请是否还在等待中
            if user_id in self.pending_requests and self.pending_requests[user_id]['status'] == 'pending':
                request_info = self.pending_requests[user_id]
                
                # 更新申请状态
                request_info['status'] = 'auto_approved'
                request_info['operator'] = 'system'
                request_info['process_time'] = int(time.time())
                
                # 调用API自动通过
                success = await self._call_set_group_add_request(request_info, True)
                
                # 发送通知
                target_group_id = self.config.get("target_group_id")
                if target_group_id:
                    auto_message = f"⏰ 用户 {nickname} ({user_id}) 的入群申请已超时自动通过"
                    await self.send_message_to_group(target_group_id, auto_message)
                
                # 清理申请记录
                await self._cleanup_request(user_id)
                
                logger.info(f"自动通过入群申请：用户 {user_id}")
                
        except Exception as e:
            logger.error(f"自动通过申请失败: {e}")
    
    async def _cleanup_request(self, user_id: str):
        """清理申请记录"""
        try:
            if user_id in self.pending_requests:
                del self.pending_requests[user_id]
                self._debug_log(f"已清理申请记录 - 用户ID: {user_id}")
        except Exception as e:
            logger.error(f"清理申请记录失败: {e}")
    
    @filter.command("帮助")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """🤖 入群申请审核插件（修复版）帮助

📋 配置指令：
• /设置源群 <群号> - 设置需要审核的群
• /设置审核群 <群号> - 设置审核消息发送的群
• /添加审核员 <QQ号> - 添加审核员
• /查看配置 - 查看当前配置

🔍 审核指令（在审核群中使用）：
• /通过 <QQ号> - 通过入群申请
• /拒绝 <QQ号> [原因] - 拒绝入群申请

🧪 测试指令：
• /测试申请 [QQ号] [群号] [申请理由] - 测试申请功能

💡 说明：
- 插件会自动监听入群申请并转发到审核群
- 支持超时自动通过功能
- 修复了NapCatQQ的flag处理问题
- 增强了调试功能和错误处理"""
        event.set_result(MessageEventResult().message(help_text))
    
    async def terminate(self):
        """插件终止时的清理工作"""
        try:
            # 清理所有待处理的申请
            self.pending_requests.clear()
            logger.info("入群申请审核插件（修复版）已终止")
        except Exception as e:
            logger.error(f"插件终止时发生错误: {e}")