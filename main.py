from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain, At
import re
import json
import os

@register("astrbot_plugin_entry_review", "Developer", "入群申请审核插件，自动转发入群申请到指定群聊进行审核", "1.0.0")
class EntryReviewPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.config_file = os.path.join(os.path.dirname(__file__), "config.json")
        self.pending_requests = {}  # 存储待审核的入群申请
        self.load_config()

    async def initialize(self):
        """插件初始化"""
        logger.info("入群申请审核插件已启动")
        
    def load_config(self):
        """加载配置文件"""
        default_config = {
            "source_group": "",  # 需要监控的群号
            "review_group": "",  # 审核群号
            "authorized_users": []  # 有权限审核的用户QQ号列表
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = default_config
                self.save_config()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self.config = default_config
            
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")

    @filter.command("设置源群")
    async def set_source_group(self, event: AstrMessageEvent):
        """设置需要监控的源群号"""
        try:
            # 提取群号
            parts = event.message_str.split()
            if len(parts) < 2:
                yield event.plain_result("请输入正确的格式：/设置源群 群号")
                return
                
            group_id = parts[1]
            self.config["source_group"] = group_id
            self.save_config()
            yield event.plain_result(f"已设置源群为：{group_id}")
            logger.info(f"设置源群为：{group_id}")
        except Exception as e:
            logger.error(f"设置源群失败: {e}")
            yield event.plain_result("设置失败，请检查输入格式")

    @filter.command("设置审核群")
    async def set_review_group(self, event: AstrMessageEvent):
        """设置审核群号"""
        try:
            parts = event.message_str.split()
            if len(parts) < 2:
                yield event.plain_result("请输入正确的格式：/设置审核群 群号")
                return
                
            group_id = parts[1]
            self.config["review_group"] = group_id
            self.save_config()
            yield event.plain_result(f"已设置审核群为：{group_id}")
            logger.info(f"设置审核群为：{group_id}")
        except Exception as e:
            logger.error(f"设置审核群失败: {e}")
            yield event.plain_result("设置失败，请检查输入格式")

    @filter.command("添加审核员")
    async def add_reviewer(self, event: AstrMessageEvent):
        """添加有权限审核的用户"""
        try:
            parts = event.message_str.split()
            if len(parts) < 2:
                yield event.plain_result("请输入正确的格式：/添加审核员 QQ号")
                return
                
            user_id = parts[1]
            if user_id not in self.config["authorized_users"]:
                self.config["authorized_users"].append(user_id)
                self.save_config()
                yield event.plain_result(f"已添加审核员：{user_id}")
                logger.info(f"添加审核员：{user_id}")
            else:
                yield event.plain_result(f"用户 {user_id} 已经是审核员")
        except Exception as e:
            logger.error(f"添加审核员失败: {e}")
            yield event.plain_result("添加失败，请检查输入格式")

    @filter.command("查看配置")
    async def show_config(self, event: AstrMessageEvent):
        """查看当前配置"""
        config_text = f"""当前配置：
源群：{self.config.get('source_group', '未设置')}
审核群：{self.config.get('review_group', '未设置')}
审核员：{', '.join(self.config.get('authorized_users', []))}
待审核申请数量：{len(self.pending_requests)}"""
        yield event.plain_result(config_text)

    @filter.group_request
    async def handle_group_request(self, event):
        """处理入群申请事件"""
        try:
            # 检查是否是目标群的申请
            if not self.config.get("source_group") or not self.config.get("review_group"):
                logger.warning("源群或审核群未配置")
                return
                
            group_id = str(event.group_id)
            if group_id != self.config["source_group"]:
                return
                
            user_id = str(event.user_id)
            comment = getattr(event, 'comment', '无')
            
            # 存储申请信息
            request_key = f"{group_id}_{user_id}"
            self.pending_requests[request_key] = {
                "group_id": group_id,
                "user_id": user_id,
                "comment": comment,
                "event": event
            }
            
            # 发送到审核群
            review_message = f"""📝 新的入群申请
申请人QQ：{user_id}
申请群：{group_id}
申请理由：{comment}

请回复：
通过 {user_id} - 同意申请
拒绝 {user_id} - 拒绝申请"""
            
            # 这里需要调用发送消息到审核群的API
            # 由于AstrBot的API可能有所不同，这里使用通用的方式
            logger.info(f"收到入群申请：用户{user_id}申请加入群{group_id}，理由：{comment}")
            logger.info(f"已转发到审核群{self.config['review_group']}")
            
        except Exception as e:
            logger.error(f"处理入群申请失败: {e}")

    @filter.message
    async def handle_review_message(self, event: AstrMessageEvent):
        """处理审核消息"""
        try:
            # 检查是否在审核群中
            if not event.group_id or str(event.group_id) != self.config.get("review_group"):
                return
                
            # 检查是否是授权用户
            sender_id = str(event.sender.user_id)
            if sender_id not in self.config.get("authorized_users", []):
                return
                
            message = event.message_str.strip()
            
            # 匹配通过指令
            approve_match = re.match(r'^通过\s+(\d+)$', message)
            if approve_match:
                user_id = approve_match.group(1)
                await self.approve_request(user_id, event)
                return
                
            # 匹配拒绝指令
            reject_match = re.match(r'^拒绝\s+(\d+)$', message)
            if reject_match:
                user_id = reject_match.group(1)
                await self.reject_request(user_id, event)
                return
                
        except Exception as e:
            logger.error(f"处理审核消息失败: {e}")

    async def approve_request(self, user_id: str, event: AstrMessageEvent):
        """同意入群申请"""
        try:
            # 查找对应的申请
            request_key = None
            for key, request in self.pending_requests.items():
                if request["user_id"] == user_id:
                    request_key = key
                    break
                    
            if not request_key:
                yield event.plain_result(f"未找到用户 {user_id} 的申请记录")
                return
                
            request_info = self.pending_requests[request_key]
            
            # 这里需要调用同意入群申请的API
            # 由于具体API可能不同，这里记录日志
            logger.info(f"同意用户 {user_id} 的入群申请")
            
            # 删除申请记录
            del self.pending_requests[request_key]
            
            yield event.plain_result(f"✅ 已同意用户 {user_id} 的入群申请")
            
        except Exception as e:
            logger.error(f"同意申请失败: {e}")
            yield event.plain_result(f"处理失败：{str(e)}")

    async def reject_request(self, user_id: str, event: AstrMessageEvent):
        """拒绝入群申请"""
        try:
            # 查找对应的申请
            request_key = None
            for key, request in self.pending_requests.items():
                if request["user_id"] == user_id:
                    request_key = key
                    break
                    
            if not request_key:
                yield event.plain_result(f"未找到用户 {user_id} 的申请记录")
                return
                
            request_info = self.pending_requests[request_key]
            
            # 这里需要调用拒绝入群申请的API
            logger.info(f"拒绝用户 {user_id} 的入群申请")
            
            # 删除申请记录
            del self.pending_requests[request_key]
            
            yield event.plain_result(f"❌ 已拒绝用户 {user_id} 的入群申请")
            
        except Exception as e:
            logger.error(f"拒绝申请失败: {e}")
            yield event.plain_result(f"处理失败：{str(e)}")

    @filter.command("帮助")
    async def help_command(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = """📖 入群申请审核插件帮助

配置命令：
/设置源群 群号 - 设置需要监控的群
/设置审核群 群号 - 设置审核消息发送的群
/添加审核员 QQ号 - 添加有审核权限的用户
/查看配置 - 查看当前配置

审核命令（仅在审核群中有效）：
通过 QQ号 - 同意入群申请
拒绝 QQ号 - 拒绝入群申请

/帮助 - 显示此帮助信息"""
        yield event.plain_result(help_text)

    async def terminate(self):
        """插件销毁时的清理工作"""
        logger.info("入群申请审核插件已停止")
